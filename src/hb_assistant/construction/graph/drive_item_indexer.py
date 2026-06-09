"""Phase 06 (Files) — rich Microsoft Graph driveItem normalization + indexing.

`normalize_drive_item` maps a raw Graph ``driveItem`` resource into the canonical
V5 ``construction_drive_items`` column set (file/folder/package facets, parent
reference, sharepointIds, change tags, hashes, deleted facet). It **never reads or
stores** ``@microsoft.graph.downloadUrl`` (a short-lived signed URL) — the field is
dropped, and the redacted package/remoteItem facet JSON strips any url-bearing keys.
Full document content is never read.

`DriveItemIndexer` performs a bounded, read-only enumeration of a source's drive
(metadata only), normalizes each item, and (on apply) upserts into V5. The
enumeration GET is asserted through the Prompt 02 read-only endpoint guard. Delta
*token* persistence + 410 rebaseline are out of scope here (Prompt 08); this is a
bounded full read for indexing and stores no delta token.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.resolver import ConstructionGraphResolver
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.files_endpoint_guard import assert_files_request_allowed
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

GRAPH_SCOPES = ["Files.ReadWrite.All", "User.Read"]
_DEFAULT_MAX_PAGES = 5
_DEFAULT_MAX_ITEMS = 500
_SAMPLE_LIMIT = 10

# Keys that must never be persisted from any facet JSON (short-lived / secret-shaped).
_FORBIDDEN_FACET_KEYS = {
    "@microsoft.graph.downloadurl",
    "@content.downloadurl",
    "downloadurl",
    "authorization",
    "access_token",
    "refresh_token",
}


def _file_extension(name: Optional[str]) -> Optional[str]:
    if not name or "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].strip().lower()
    return ext or None


def _redact_facet(facet: Any) -> Optional[dict[str, Any]]:
    """Keep a shallow metadata view of a facet, dropping any url/token-bearing keys."""
    if not isinstance(facet, dict):
        return None
    out: dict[str, Any] = {}
    for k, v in facet.items():
        if k.lower() in _FORBIDDEN_FACET_KEYS:
            continue
        if isinstance(v, str) and ("downloadurl" in k.lower() or k.lower().endswith("url")):
            # Drop any URL-bearing value (signed URLs are short-lived / replayable).
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
    return out or None


def _string_or_none(value: Any) -> Optional[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _parent_folder_name(path: Any) -> Optional[str]:
    raw_path = _string_or_none(path)
    if raw_path is None:
        return None
    folder_path = raw_path.split(":", 1)[1] if ":" in raw_path else raw_path
    parts = [p for p in folder_path.strip("/").split("/") if p]
    return parts[-1] if parts else None


def _last_modified_by_fields(raw: dict[str, Any]) -> dict[str, Optional[str]]:
    identity = raw.get("lastModifiedBy")
    if not isinstance(identity, dict):
        return {
            "last_modified_by_display_name": None,
            "last_modified_by_user_id": None,
            "last_modified_by_email": None,
            "last_modified_by_application_display_name": None,
            "last_modified_by_raw_json": None,
        }
    user = identity.get("user") if isinstance(identity.get("user"), dict) else {}
    app = identity.get("application") if isinstance(identity.get("application"), dict) else {}
    email = _string_or_none(user.get("email")) or _string_or_none(user.get("userPrincipalName"))
    return {
        "last_modified_by_display_name": _string_or_none(user.get("displayName")),
        "last_modified_by_user_id": _string_or_none(user.get("id")),
        "last_modified_by_email": email,
        "last_modified_by_application_display_name": _string_or_none(app.get("displayName")),
        "last_modified_by_raw_json": json.dumps(identity, sort_keys=True),
    }


def normalize_drive_item(
    source_id: str,
    drive_id: str,
    raw: dict[str, Any],
    *,
    project_key: Optional[str] = None,
) -> dict[str, Any]:
    """Map a raw Graph driveItem to canonical ``upsert_drive_item`` kwargs.

    ``@microsoft.graph.downloadUrl`` and any url/token-bearing facet keys are
    dropped. Missing optional fields normalize to ``None``/``0``/``False``.
    """
    file_facet = raw.get("file") if isinstance(raw.get("file"), dict) else None
    folder_facet = raw.get("folder") if isinstance(raw.get("folder"), dict) else None
    package_facet = raw.get("package") if isinstance(raw.get("package"), dict) else None
    remote_facet = raw.get("remoteItem") if isinstance(raw.get("remoteItem"), dict) else None
    parent_ref = raw.get("parentReference") if isinstance(raw.get("parentReference"), dict) else {}
    sp_ids = raw.get("sharepointIds") if isinstance(raw.get("sharepointIds"), dict) else {}

    is_folder = folder_facet is not None
    is_package = package_facet is not None
    is_file = (file_facet is not None) and not is_folder and not is_package

    hashes = (
        file_facet.get("hashes")
        if file_facet and isinstance(file_facet.get("hashes"), dict)
        else None
    )
    quick_xor = hashes.get("quickXorHash") if hashes else None
    name = raw.get("name")
    parent_reference_path = (parent_ref or {}).get("path")

    return {
        "source_id": source_id,
        "drive_id": (parent_ref or {}).get("driveId") or drive_id,
        "drive_item_id": raw.get("id"),
        "parent_drive_item_id": (parent_ref or {}).get("id"),
        "site_id": (sp_ids or {}).get("siteId"),
        "list_id": (sp_ids or {}).get("listId"),
        "list_item_id": (sp_ids or {}).get("listItemId"),
        "name": name,
        "path": (parent_ref or {}).get("path"),
        "web_url": raw.get("webUrl"),
        "is_folder": is_folder,
        "is_file": is_file,
        "is_package": is_package,
        "file_extension": _file_extension(name) if is_file else None,
        "mime_type": (file_facet or {}).get("mimeType") if file_facet else None,
        "size_bytes": raw.get("size"),
        "created_datetime": raw.get("createdDateTime"),
        "last_modified_datetime": raw.get("lastModifiedDateTime"),
        "e_tag": raw.get("eTag"),
        "c_tag": raw.get("cTag"),
        "quick_xor_hash": quick_xor,
        "project_key": project_key,
        "file_hashes_json": json.dumps(hashes, sort_keys=True) if hashes else None,
        "deleted": raw.get("deleted") is not None,
        "parent_reference_path": parent_reference_path,
        "parent_folder_name": _parent_folder_name(parent_reference_path),
        "folder_child_count": (folder_facet or {}).get("childCount") if folder_facet else None,
        "sharepoint_web_id": (sp_ids or {}).get("webId"),
        "sharepoint_list_item_id": (sp_ids or {}).get("listItemId"),
        "package_json_redacted": (
            json.dumps(_redact_facet(package_facet), sort_keys=True) if package_facet else None
        ),
        "remote_item_json_redacted": (
            json.dumps(_redact_facet(remote_facet), sort_keys=True) if remote_facet else None
        ),
        **_last_modified_by_fields(raw),
    }


def redacted_sample(kwargs: dict[str, Any]) -> dict[str, Any]:
    """A compact, content-free preview of a normalized item for dry-run evidence."""
    return {
        "drive_item_id": kwargs.get("drive_item_id"),
        "name_present": bool(kwargs.get("name")),
        "is_file": kwargs.get("is_file"),
        "is_folder": kwargs.get("is_folder"),
        "is_package": kwargs.get("is_package"),
        "deleted": kwargs.get("deleted"),
        "size_bytes": kwargs.get("size_bytes"),
        "file_extension": kwargs.get("file_extension"),
        "last_modified_datetime": kwargs.get("last_modified_datetime"),
        "parent_reference_path_present": bool(kwargs.get("parent_reference_path")),
        "parent_folder_name_present": bool(kwargs.get("parent_folder_name")),
        "project_key_present": bool(kwargs.get("project_key")),
        "last_modified_by_present": bool(kwargs.get("last_modified_by_display_name")),
    }


class IndexReport(BaseModel):
    source_id: str
    kind: str
    drive_id: Optional[str] = None
    folder_item_id: Optional[str] = None
    endpoint: Optional[str] = None
    status: str  # indexed | pending | unsupported | error
    items_seen: int = 0
    items_persisted: int = 0
    pages_seen: int = 0
    sample: list[dict[str, Any]] = Field(default_factory=list)
    download_url_persisted: bool = False
    note: Optional[str] = None
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class DriveItemIndexer:
    """Bounded read-only driveItem enumeration → rich V5 normalization/persistence."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: Optional[ConstructionStore] = None,
    ) -> None:
        self._http = http_client
        self._store = store
        self._resolver = ConstructionGraphResolver(http_client)

    def _select_endpoint(self, res: Any) -> Optional[str]:
        if res.drive_id and res.folder_item_id:
            return f"/drives/{res.drive_id}/items/{res.folder_item_id}/delta"
        if res.drive_id:
            return f"/drives/{res.drive_id}/root/delta"
        if res.kind in {"onedrive_business_root", "onedrive_personal_root", "onedrive_personal"}:
            return "/me/drive/root/delta"
        return None

    def index(
        self,
        source: SourceLocation,
        *,
        dry_run: bool = True,
        max_pages: int = _DEFAULT_MAX_PAGES,
        max_items: int = _DEFAULT_MAX_ITEMS,
    ) -> IndexReport:
        res = self._resolver.resolve(source)
        if res.status in {"unsupported"}:
            return IndexReport(source_id=source.source_key, kind=source.kind, status="unsupported")
        endpoint = self._select_endpoint(res)
        if endpoint is None:
            return IndexReport(
                source_id=source.source_key,
                kind=source.kind,
                drive_id=res.drive_id,
                status="pending",
                note=res.error_redacted or "drive_id unresolved; cannot index",
            )

        # Read-only guard before any HTTP read.
        assert_files_request_allowed("GET", endpoint)

        items_seen = 0
        persisted = 0
        pages_seen = 0
        sample: list[dict[str, Any]] = []
        download_url_persisted = False
        try:
            for item in self._http.get_all_pages(
                endpoint,
                params={"$top": str(min(max_items, 200))},
                scopes=GRAPH_SCOPES,
                max_pages=max_pages,
                max_items=max_items,
            ):
                items_seen += 1
                kwargs = normalize_drive_item(
                    source.source_key,
                    res.drive_id or "",
                    item,
                    project_key=source.project_key,
                )
                if not kwargs.get("drive_item_id"):
                    continue
                # Hard proof: the normalized payload never carries a download URL.
                if any("downloadurl" in str(k).lower() for k in kwargs):
                    download_url_persisted = True
                if len(sample) < _SAMPLE_LIMIT:
                    sample.append(redacted_sample(kwargs))
                if not dry_run and self._store is not None:
                    self._store.upsert_drive_item(**kwargs)
                    persisted += 1
        except GraphHttpError as e:
            return IndexReport(
                source_id=source.source_key,
                kind=source.kind,
                drive_id=res.drive_id,
                folder_item_id=res.folder_item_id,
                endpoint=endpoint,
                status="error",
                items_seen=items_seen,
                error_redacted=f"graph_{e.status}",
            )

        report = IndexReport(
            source_id=source.source_key,
            kind=source.kind,
            drive_id=res.drive_id,
            folder_item_id=res.folder_item_id,
            endpoint=endpoint,
            status="indexed",
            items_seen=items_seen,
            items_persisted=persisted,
            pages_seen=pages_seen,
            sample=sample,
            download_url_persisted=download_url_persisted,
        )
        if not dry_run and self._store is not None:
            self._store.insert_processing_receipt(
                receipt_id=str(uuid.uuid4()),
                source_id=source.source_key,
                operation="drive_item_index",
                status=report.status,
                detail=report.model_dump(),
            )
        return report
