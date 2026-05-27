"""Resolve registered SourceLocation entries to canonical Graph identifiers.

Read-only. Never mutates the source system; only resolves URLs/paths into
canonical IDs (`site_id`, `drive_id`) that the delta crawler will use.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import unquote, urlparse

from pydantic import BaseModel

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

GRAPH_SCOPES = ["Sites.Read.All", "Files.Read.All", "User.Read"]

_SUPPORTED_KINDS = {"sharepoint_site", "onedrive_personal"}


class ResolutionResult(BaseModel):
    source_key: str
    kind: str
    status: str  # "resolved" | "pending" | "unsupported" | "error"
    site_id: Optional[str] = None
    drive_id: Optional[str] = None
    web_url: Optional[str] = None
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
    """Resolve registered sources to Graph site_id / drive_id."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: Optional[ConstructionStore] = None,
    ) -> None:
        self._http = http_client
        self._store = store

    def resolve(self, source: SourceLocation, *, apply: bool = False) -> ResolutionResult:
        if source.kind not in _SUPPORTED_KINDS:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                status="unsupported",
                error_redacted=f"kind {source.kind!r} not yet supported by resolver",
            )

        try:
            if source.kind == "sharepoint_site":
                result = self._resolve_sharepoint_site(source)
            else:
                result = self._resolve_onedrive_personal(source)
        except GraphHttpError as e:
            result = ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                status="error",
                error_redacted=f"graph_{e.status}: {e.message[:120]}",
            )
        except ValueError as e:
            result = ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
                status="error",
                error_redacted=str(e)[:200],
            )

        if apply and self._store is not None and result.status in {"resolved", "pending"}:
            self._store.upsert_resolution(
                source_key=result.source_key,
                kind=result.kind,
                site_id=result.site_id,
                drive_id=result.drive_id,
                web_url=result.web_url,
                resolution_status=result.status,
            )
        return result

    def _resolve_sharepoint_site(self, source: SourceLocation) -> ResolutionResult:
        if not source.site_url:
            return ResolutionResult(
                source_key=source.source_key,
                kind=source.kind,
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
            status=status,
            site_id=site_id,
            drive_id=drive_id,
            web_url=web_url,
        )

    def _resolve_onedrive_personal(self, source: SourceLocation) -> ResolutionResult:
        drive_data = self._http.get(
            "/me/drive",
            params={"$select": "id,webUrl"},
            scopes=GRAPH_SCOPES,
        )
        drive_id = drive_data.get("id")
        web_url = drive_data.get("webUrl")
        status = "resolved" if drive_id else "pending"
        return ResolutionResult(
            source_key=source.source_key,
            kind=source.kind,
            status=status,
            drive_id=drive_id,
            web_url=web_url,
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
