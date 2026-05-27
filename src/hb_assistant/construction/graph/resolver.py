"""Resolve registered SourceLocation entries to canonical Graph identifiers.

Read-only. Never mutates the source system; only resolves URLs/paths into
canonical IDs (``site_id``, ``drive_id``, ``folder_item_id``) that the delta
crawler will use.

Phase 02 scope-aware dispatch:

- ``sharepoint_site``, ``sharepoint_library`` (legacy)            → site + drive resolution.
- ``sharepoint_project_drive_folder``                              → site + drive + folder
                                                                     resolution; canonical
                                                                     pre-populated IDs fast-path
                                                                     to ``pre_resolved`` without
                                                                     any HTTP call.
- ``sharepoint_site_page``                                         → site_id only; page_id
                                                                     resolution deferred to a
                                                                     dedicated page crawler.
- ``onedrive_personal`` (legacy), ``onedrive_personal_root``       → /me/drive.
- ``onedrive_business_root``                                       → /me/drive (delegated
                                                                     business token); driveType
                                                                     surfaced for visibility.
- ``onedrive_shared`` (legacy), ``onedrive_shared_library``        → pre_resolved when drive_id
                                                                     present; otherwise pending
                                                                     (shared-library lookup
                                                                     needs share URL or remote
                                                                     item context).
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from urllib.parse import unquote, urlparse

from pydantic import BaseModel

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

GRAPH_SCOPES = ["Sites.Read.All", "Files.Read.All", "User.Read"]


class ResolutionResult(BaseModel):
    source_key: str
    kind: str
    status: str  # "resolved" | "pre_resolved" | "pending" | "unsupported" | "error"
    site_id: Optional[str] = None
    drive_id: Optional[str] = None
    folder_item_id: Optional[str] = None
    page_id: Optional[str] = None
    web_url: Optional[str] = None
    scope: Optional[str] = None
    note: Optional[str] = None
    pre_resolved: bool = False
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


def _parse_sharepoint_url(site_url: str) -> tuple[str, str]:
    """Split a SharePoint web URL into (hostname, server_relative_path).

    Example: https://contoso.sharepoint.com/sites/Tropical → ("contoso.sharepoint.com", "/sites/Tropical").
    """
    parsed = urlparse(site_url)
    if not parsed.hostname:
        raise ValueError(f"site_url {site_url!r} missing hostname")
    path = unquote(parsed.path).rstrip("/")
    if not path:
        raise ValueError(f"site_url {site_url!r} missing site path (expected /sites/<name>)")
    return parsed.hostname, path


class ConstructionGraphResolver:
    """Resolve registered sources to Graph site_id / drive_id / folder_item_id.

    Per-scope dispatch goes through :pyattr:`_DISPATCH`; canonical Phase 02
    scopes that ship with pre-populated identifiers fast-path to
    ``pre_resolved`` and never touch the HTTP client.
    """

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: Optional[ConstructionStore] = None,
    ) -> None:
        self._http = http_client
        self._store = store

    @property
    def _dispatch(self) -> dict[str, Callable[[SourceLocation], ResolutionResult]]:
        return {
            "sharepoint_site": self._resolve_sharepoint_site,
            "sharepoint_library": self._resolve_sharepoint_site,
            "sharepoint_project_drive_folder": self._resolve_sharepoint_project_drive_folder,
            "sharepoint_site_page": self._resolve_sharepoint_site_page,
            "onedrive_personal": self._resolve_onedrive_personal_root,
            "onedrive_personal_root": self._resolve_onedrive_personal_root,
            "onedrive_business_root": self._resolve_onedrive_business_root,
            "onedrive_shared": self._resolve_onedrive_shared_library,
            "onedrive_shared_library": self._resolve_onedrive_shared_library,
        }

    def supported_kinds(self) -> set[str]:
        return set(self._dispatch.keys())

    def resolve(self, source: SourceLocation, *, apply: bool = False) -> ResolutionResult:
        handler = self._dispatch.get(source.kind)
        if handler is None:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="unsupported",
                error_redacted=f"kind {source.kind!r} not yet supported by resolver",
            )

        try:
            result = handler(source)
        except GraphHttpError as e:
            result = ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="error",
                error_redacted=f"graph_{e.status}: {e.message[:120]}",
            )
        except ValueError as e:
            result = ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="error",
                error_redacted=str(e)[:200],
            )

        # Always carry scope for downstream summaries.
        if result.scope is None:
            result.scope = source.kind

        if (
            apply
            and self._store is not None
            and result.status in {"resolved", "pre_resolved", "pending"}
        ):
            # V2 store is the durable target; V5 source_locations adoption is
            # gated on downstream caller migration.
            self._store.upsert_resolution(
                source_key=result.source_key,
                kind=result.kind,
                site_id=result.site_id,
                drive_id=result.drive_id,
                web_url=result.web_url,
                resolution_status=(
                    "resolved" if result.status == "pre_resolved" else result.status
                ),
            )
        return result

    # ------------------------------------------------------------------
    # SharePoint site / library / project-drive folder.
    # ------------------------------------------------------------------

    def _resolve_sharepoint_site(self, source: SourceLocation) -> ResolutionResult:
        if not source.site_url:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="pending",
                error_redacted="site_url not set; cannot resolve",
            )

        hostname, path = _parse_sharepoint_url(source.site_url)
        site_data = self._http.get(
            f"/sites/{hostname}:{path}",
            params={"$select": "id,webUrl,name"},
            scopes=GRAPH_SCOPES,
        )
        site_id = site_data.get("id")
        web_url = site_data.get("webUrl") or source.site_url

        drive_id: Optional[str] = None
        if site_id:
            drive_data = self._http.get(
                f"/sites/{site_id}/drive",
                params={"$select": "id,webUrl"},
                scopes=GRAPH_SCOPES,
            )
            drive_id = drive_data.get("id")

        status = "resolved" if (site_id and drive_id) else "pending"
        return ResolutionResult(
            source_key=source.source_key,
            kind=source.kind,
            scope=source.kind,
            status=status,
            site_id=site_id,
            drive_id=drive_id,
            web_url=web_url,
        )

    def _resolve_sharepoint_project_drive_folder(
        self, source: SourceLocation
    ) -> ResolutionResult:
        # Canonical fast-path: pre-populated IDs short-circuit to pre_resolved
        # without any Graph HTTP call.
        if source.site_id and source.drive_id and source.folder_item_id:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="pre_resolved",
                pre_resolved=True,
                site_id=source.site_id,
                drive_id=source.drive_id,
                folder_item_id=source.folder_item_id,
                web_url=source.folder_web_url or source.site_url,
                note="canonical_identifiers_pre_populated",
            )

        if not source.site_url:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="pending",
                error_redacted="site_url not set; cannot resolve project drive folder",
            )

        hostname, path = _parse_sharepoint_url(source.site_url)
        site_id = source.site_id
        web_url: Optional[str] = source.site_url
        if not site_id:
            site_data = self._http.get(
                f"/sites/{hostname}:{path}",
                params={"$select": "id,webUrl,name"},
                scopes=GRAPH_SCOPES,
            )
            site_id = site_data.get("id")
            web_url = site_data.get("webUrl") or source.site_url

        drive_id = source.drive_id
        if site_id and not drive_id:
            drive_data = self._http.get(
                f"/sites/{site_id}/drive",
                params={"$select": "id,webUrl"},
                scopes=GRAPH_SCOPES,
            )
            drive_id = drive_data.get("id")

        folder_item_id = source.folder_item_id
        note: Optional[str] = None
        if drive_id and not folder_item_id:
            if source.root_path or source.folder_path:
                folder_rel = source.root_path or source.folder_path or ""
                folder_data = self._http.get(
                    f"/drives/{drive_id}/root:{folder_rel}",
                    params={"$select": "id,webUrl,name"},
                    scopes=GRAPH_SCOPES,
                )
                folder_item_id = folder_data.get("id")
                web_url = folder_data.get("webUrl") or web_url
            else:
                note = "folder_item_id_resolution_requires_folder_path"

        status = (
            "resolved"
            if (site_id and drive_id and folder_item_id)
            else "pending"
        )
        return ResolutionResult(
            source_key=source.source_key,
            kind=source.kind,
            scope=source.kind,
            status=status,
            site_id=site_id,
            drive_id=drive_id,
            folder_item_id=folder_item_id,
            web_url=web_url,
            note=note,
        )

    def _resolve_sharepoint_site_page(self, source: SourceLocation) -> ResolutionResult:
        if not source.site_url:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="pending",
                error_redacted="site_url not set; cannot resolve site_page",
            )

        hostname, path = _parse_sharepoint_url(source.site_url)
        site_id = source.site_id
        web_url = source.site_url
        if not site_id:
            site_data = self._http.get(
                f"/sites/{hostname}:{path}",
                params={"$select": "id,webUrl,name"},
                scopes=GRAPH_SCOPES,
            )
            site_id = site_data.get("id")
            web_url = site_data.get("webUrl") or source.site_url

        # page_id resolution is intentionally deferred to a dedicated
        # page crawler (separate prompt). We carry the site_id so that
        # downstream page crawl can resume without re-resolving.
        return ResolutionResult(
            source_key=source.source_key,
            kind=source.kind,
            scope=source.kind,
            status="pending",
            site_id=site_id,
            web_url=web_url,
            note="page_id_resolution_deferred_to_page_crawler",
        )

    # ------------------------------------------------------------------
    # OneDrive scopes.
    # ------------------------------------------------------------------

    def _resolve_onedrive_personal_root(self, source: SourceLocation) -> ResolutionResult:
        return self._resolve_me_drive(source, expected_drive_type="personal")

    def _resolve_onedrive_business_root(self, source: SourceLocation) -> ResolutionResult:
        return self._resolve_me_drive(source, expected_drive_type="business")

    def _resolve_me_drive(
        self, source: SourceLocation, *, expected_drive_type: str
    ) -> ResolutionResult:
        drive_data = self._http.get(
            "/me/drive",
            params={"$select": "id,webUrl,driveType"},
            scopes=GRAPH_SCOPES,
        )
        drive_id = drive_data.get("id")
        web_url = drive_data.get("webUrl")
        drive_type = drive_data.get("driveType")
        status = "resolved" if drive_id else "pending"
        note = (
            f"drive_type={drive_type!r}"
            if drive_type
            else f"expected_drive_type={expected_drive_type!r}; driveType_missing"
        )
        return ResolutionResult(
            source_key=source.source_key,
            kind=source.kind,
            scope=source.kind,
            status=status,
            drive_id=drive_id,
            web_url=web_url,
            note=note,
        )

    def _resolve_onedrive_shared_library(self, source: SourceLocation) -> ResolutionResult:
        if source.drive_id:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                scope=source.kind,
                status="pre_resolved",
                pre_resolved=True,
                drive_id=source.drive_id,
                web_url=source.folder_web_url or source.site_url,
                note="canonical_drive_id_pre_populated",
            )
        return ResolutionResult(
            source_key=source.source_key,
            kind=source.kind,
            scope=source.kind,
            status="pending",
            note="drive_id_resolution_requires_share_url_or_remote_item_lookup",
        )


def _redact_item_preview(item: dict[str, Any]) -> dict[str, Any]:
    """Return a safe metadata-only preview (no body/text/excerpt)."""
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "is_folder": bool(item.get("folder")),
        "size": item.get("size"),
        "last_modified": item.get("lastModifiedDateTime"),
        "deleted": item.get("deleted") is not None,
    }
