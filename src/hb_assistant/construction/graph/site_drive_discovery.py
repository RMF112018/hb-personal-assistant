"""Phase 06 (Files) — SharePoint + OneDrive source discovery (metadata-only).

Resolves approved SharePoint sites and enumerates their document-library drives,
matching a configured :class:`SourceLocation` to a concrete drive by ``drive_id``,
``list_id``, ``library_name``, ``webUrl``, or an explicit default-drive fallback.
No content crawl: only ``/sites/{id}/drive`` and ``/sites/{id}/drives`` are read;
``/items``/``/content`` are never touched here.

Site resolution reuses :class:`ConstructionGraphResolver` (URL + pre-seeded ID +
ProjectHome linked-source candidates). The drive-enumeration reads issued by this
service are asserted through :func:`assert_files_request_allowed` (the Prompt 02
read-only endpoint guard) before the HTTP GET, so a non-GET / mutation path can
never be issued from this path.

The only local side effect is an optional ``construction_processing_receipts``
row on ``apply``. No tokens, signed URLs, raw delta links,
``@microsoft.graph.downloadUrl``, or document content are read, returned, or
persisted.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.resolver import (
    GRAPH_SCOPES,
    GRAPH_SCOPES_DRIVE,
    ConstructionGraphResolver,
    _parse_sharepoint_url,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.files_endpoint_guard import assert_files_request_allowed
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

# Discovery is bounded and never crawls content (mirrors the package
# sharepoint_onedrive_discovery_defaults.json posture).
_DEFAULT_MAX_DRIVES = 500
_SHAREPOINT_KINDS = {
    "sharepoint_site",
    "sharepoint_library",
    "sharepoint_project_drive_folder",
    "sharepoint_site_page",
}
_ONEDRIVE_ROOT_KINDS = {
    "onedrive_personal",
    "onedrive_personal_root",
    "onedrive_business_root",
}
_ONEDRIVE_SHARED_KINDS = {"onedrive_shared", "onedrive_shared_library"}
_ONEDRIVE_KINDS = _ONEDRIVE_ROOT_KINDS | _ONEDRIVE_SHARED_KINDS


class SiteDiscoveryResult(BaseModel):
    source_id: str
    kind: str
    site_url: Optional[str] = None
    hostname: Optional[str] = None
    server_relative_path: Optional[str] = None
    site_id: Optional[str] = None
    web_url: Optional[str] = None
    status: str  # pre_resolved | resolved | pending | unsupported | error
    pre_resolved: bool = False
    note: Optional[str] = None
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class DriveCandidate(BaseModel):
    drive_id: str
    name: Optional[str] = None
    web_url: Optional[str] = None
    drive_type: Optional[str] = None
    list_id: Optional[str] = None

    model_config = {"extra": "forbid"}


class DriveDiscoveryResult(BaseModel):
    source_id: str
    kind: str
    site_id: Optional[str] = None
    matched_drive: Optional[DriveCandidate] = None
    match_method: Optional[str] = (
        None  # drive_id | list_id | library_name | web_url | default_drive
    )
    match_confidence: Optional[str] = None  # high | medium | low | none
    candidates: list[DriveCandidate] = Field(default_factory=list)
    linked_sources: list[dict[str, Any]] = Field(default_factory=list)
    status: str  # matched | unmatched | pending | unsupported | error
    note: Optional[str] = None
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class OneDriveDiscoveryResult(BaseModel):
    source_id: str
    kind: str
    drive_id: Optional[str] = None
    drive_type: Optional[str] = None
    web_url: Optional[str] = None
    # pre_resolved | resolved | pending | unavailable | requires_share_url | unsupported | error
    status: str
    resolution_status: Optional[str] = None
    available_drives: list[DriveCandidate] = Field(default_factory=list)
    note: Optional[str] = None
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


def _candidate_from_entry(entry: dict[str, Any]) -> Optional[DriveCandidate]:
    drive_id = entry.get("id")
    if not drive_id:
        return None
    list_obj = entry.get("list") if isinstance(entry.get("list"), dict) else {}
    return DriveCandidate(
        drive_id=drive_id,
        name=entry.get("name"),
        web_url=entry.get("webUrl"),
        drive_type=entry.get("driveType"),
        list_id=(list_obj or {}).get("id"),
    )


class SiteDriveDiscovery:
    """Site resolution + drive enumeration/matching, metadata-only."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: Optional[ConstructionStore] = None,
    ) -> None:
        self._http = http_client
        self._store = store
        self._resolver = ConstructionGraphResolver(http_client)

    # -- site ---------------------------------------------------------------

    def discover_site(self, source: SourceLocation, *, apply: bool = False) -> SiteDiscoveryResult:
        if source.kind not in _SHAREPOINT_KINDS:
            return SiteDiscoveryResult(
                source_id=source.source_key,
                kind=source.kind,
                status="unsupported",
                note="not a SharePoint source kind",
            )

        hostname: Optional[str] = None
        server_rel: Optional[str] = None
        if source.site_url:
            try:
                hostname, server_rel = _parse_sharepoint_url(source.site_url)
            except ValueError:
                hostname, server_rel = None, None

        try:
            res = self._resolver.resolve(source)
        except GraphHttpError as e:
            result = SiteDiscoveryResult(
                source_id=source.source_key,
                kind=source.kind,
                site_url=source.site_url,
                hostname=hostname,
                server_relative_path=server_rel,
                status="error",
                error_redacted=f"graph_{e.status}",
            )
            self._maybe_persist(result.source_id, "site_discovery", result.status, result, apply)
            return result

        result = SiteDiscoveryResult(
            source_id=source.source_key,
            kind=source.kind,
            site_url=source.site_url,
            hostname=hostname,
            server_relative_path=server_rel,
            site_id=res.site_id,
            web_url=res.web_url,
            status=res.status,
            pre_resolved=res.pre_resolved,
            note=res.note or res.error_redacted,
        )
        self._maybe_persist(result.source_id, "site_discovery", result.status, result, apply)
        return result

    # -- drives -------------------------------------------------------------

    def discover_drives(
        self, source: SourceLocation, *, apply: bool = False
    ) -> DriveDiscoveryResult:
        if source.kind not in _SHAREPOINT_KINDS:
            return DriveDiscoveryResult(
                source_id=source.source_key,
                kind=source.kind,
                status="unsupported",
                note="not a SharePoint source kind",
            )

        try:
            res = self._resolver.resolve(source)
        except GraphHttpError as e:
            result = DriveDiscoveryResult(
                source_id=source.source_key,
                kind=source.kind,
                status="error",
                error_redacted=f"graph_{e.status}",
            )
            self._maybe_persist(result.source_id, "drive_discovery", result.status, result, apply)
            return result

        # Site-page sources surface linked libraries (metadata-only) rather than
        # a single matched project drive.
        if source.kind == "sharepoint_site_page":
            result = DriveDiscoveryResult(
                source_id=source.source_key,
                kind=source.kind,
                site_id=res.site_id,
                linked_sources=[c.model_dump() for c in res.linked_sources_discovered],
                status="matched" if res.linked_sources_discovered else "pending",
                note=res.note or "site_page linked-source candidates (metadata-only)",
            )
            self._maybe_persist(result.source_id, "drive_discovery", result.status, result, apply)
            return result

        site_id = res.site_id
        if not site_id:
            result = DriveDiscoveryResult(
                source_id=source.source_key,
                kind=source.kind,
                site_id=None,
                status="pending",
                note=res.error_redacted or "site_id unresolved; cannot enumerate drives",
            )
            self._maybe_persist(result.source_id, "drive_discovery", result.status, result, apply)
            return result

        candidates, enum_note = self._enumerate_drives(site_id)
        matched, method, confidence = _match_drive(source, candidates)
        status = "matched" if matched else "unmatched"
        result = DriveDiscoveryResult(
            source_id=source.source_key,
            kind=source.kind,
            site_id=site_id,
            matched_drive=matched,
            match_method=method,
            match_confidence=confidence,
            candidates=candidates,
            status=status,
            note=enum_note,
        )
        self._maybe_persist(result.source_id, "drive_discovery", result.status, result, apply)
        return result

    # -- onedrive -----------------------------------------------------------

    def discover_onedrive(
        self, source: SourceLocation, *, apply: bool = False
    ) -> OneDriveDiscoveryResult:
        if source.kind not in _ONEDRIVE_KINDS:
            return OneDriveDiscoveryResult(
                source_id=source.source_key,
                kind=source.kind,
                status="unsupported",
                note="not a OneDrive source kind",
            )

        # Shared libraries: pre_resolved when a drive_id is configured; otherwise
        # represented as requires_share_url. Never force resolution / fabricate a URL.
        if source.kind in _ONEDRIVE_SHARED_KINDS:
            if source.drive_id:
                result = OneDriveDiscoveryResult(
                    source_id=source.source_key,
                    kind=source.kind,
                    drive_id=source.drive_id,
                    web_url=source.folder_web_url or source.site_url,
                    status="pre_resolved",
                    resolution_status=source.resolution_status,
                    note="canonical_drive_id_pre_populated",
                )
            else:
                result = OneDriveDiscoveryResult(
                    source_id=source.source_key,
                    kind=source.kind,
                    status="requires_share_url",
                    resolution_status=source.resolution_status,
                    note="drive_id_resolution_requires_share_url_or_remote_item_lookup; not forced",
                )
            self._maybe_persist(
                result.source_id, "onedrive_discovery", result.status, result, apply
            )
            return result

        # Personal/business root: resolve /me/drive (primary), then enumerate
        # /me/drives (supplementary). A 404 on /me/drive => unavailable.
        res = self._resolver.resolve(source)
        status = res.status
        note = res.note
        error_redacted: Optional[str] = None
        if res.status == "error":
            if (res.error_redacted or "").startswith("graph_404"):
                status = "unavailable"
                note = "me_drive_unavailable_or_not_provisioned"
            else:
                error_redacted = res.error_redacted

        available, enum_note = self._enumerate_me_drives()
        drive_type: Optional[str] = None
        for c in available:
            if c.drive_id and c.drive_id == res.drive_id:
                drive_type = c.drive_type
                break

        combined = "; ".join(n for n in (note, enum_note) if n) or None
        result = OneDriveDiscoveryResult(
            source_id=source.source_key,
            kind=source.kind,
            drive_id=res.drive_id,
            drive_type=drive_type,
            web_url=res.web_url,
            status=status,
            resolution_status=source.resolution_status,
            available_drives=available,
            note=combined,
            error_redacted=error_redacted,
        )
        self._maybe_persist(result.source_id, "onedrive_discovery", result.status, result, apply)
        return result

    def _enumerate_me_drives(self) -> tuple[list[DriveCandidate], Optional[str]]:
        path = "/me/drives"
        # Read-only guard: refuse anything that is not an allowlisted GET before HTTP.
        assert_files_request_allowed("GET", path)
        try:
            data = self._http.get(
                path,
                params={"$select": "id,name,driveType,webUrl"},
                # OneDrive enumeration is drive-scoped (no admin-restricted Sites.Read.All).
                scopes=GRAPH_SCOPES_DRIVE,
            )
        except GraphHttpError as e:
            return [], f"me_drives_enumeration_failed: graph_{e.status}"

        candidates: list[DriveCandidate] = []
        for entry in (data.get("value") or [])[:_DEFAULT_MAX_DRIVES]:
            cand = _candidate_from_entry(entry)
            if cand is not None:
                candidates.append(cand)
        return candidates, None

    def _enumerate_drives(self, site_id: str) -> tuple[list[DriveCandidate], Optional[str]]:
        path = f"/sites/{site_id}/drives"
        # Read-only guard: refuse anything that is not an allowlisted GET before HTTP.
        assert_files_request_allowed("GET", path)
        try:
            data = self._http.get(
                path,
                params={"$select": "id,name,webUrl,driveType"},
                scopes=GRAPH_SCOPES,
            )
        except GraphHttpError as e:
            return [], f"drive_enumeration_failed: graph_{e.status}"

        candidates: list[DriveCandidate] = []
        for entry in (data.get("value") or [])[:_DEFAULT_MAX_DRIVES]:
            cand = _candidate_from_entry(entry)
            if cand is not None:
                candidates.append(cand)
        return candidates, None

    # -- persistence --------------------------------------------------------

    def _maybe_persist(
        self,
        source_id: str,
        operation: str,
        status: str,
        result: BaseModel,
        apply: bool,
    ) -> None:
        if not apply or self._store is None:
            return
        self._store.insert_processing_receipt(
            receipt_id=str(uuid.uuid4()),
            source_id=source_id,
            operation=operation,
            status=status,
            detail=result.model_dump(),
        )


def _match_drive(
    source: SourceLocation, candidates: list[DriveCandidate]
) -> tuple[Optional[DriveCandidate], Optional[str], Optional[str]]:
    """Match a configured source to one enumerated drive by precedence.

    Precedence: drive_id (high) > list_id (high) > library_name (medium) >
    webUrl (medium) > explicit default-drive fallback (low). Returns
    ``(matched_drive, match_method, match_confidence)`` or ``(None, None, "none")``.
    """
    if not candidates:
        return None, None, "none"

    if source.drive_id:
        for c in candidates:
            if c.drive_id == source.drive_id:
                return c, "drive_id", "high"

    if source.list_id:
        for c in candidates:
            if c.list_id and c.list_id == source.list_id:
                return c, "list_id", "high"

    if source.library_name:
        target = source.library_name.casefold()
        for c in candidates:
            if c.name and c.name.casefold() == target:
                return c, "library_name", "medium"

    web_target = source.folder_web_url or source.site_url
    if web_target:
        wt = web_target.rstrip("/").lower()
        for c in candidates:
            if c.web_url and wt.startswith(c.web_url.rstrip("/").lower()):
                return c, "web_url", "medium"

    return None, None, "none"
