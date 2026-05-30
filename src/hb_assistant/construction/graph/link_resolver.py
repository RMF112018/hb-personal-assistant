"""Phase 06A — user-provided OneDrive/SharePoint link → canonical ID resolution.

Accepts a browser sharing link and returns the canonical IDs the Phase 06 pipeline
needs (site_id / drive_id / drive_item_id / folder_item_id / parent ids / list ids).

Primary path: the Microsoft Graph **Shares API** — encode the URL to the ``u!``
unpadded-base64url share token and read ``GET /shares/{encoded}/driveItem``
(metadata only, ``$select``). This is read-only **resolution**, never sharing-link
**redemption**: no ``Prefer: redeemSharingLink`` header is ever sent (the shared
``GraphHttpClient.get`` cannot send custom headers). Fallbacks: ``/me/drive`` for an
own-OneDrive-root link, and a source-registry host/path match.

Safety: the raw tokenized URL is never returned or persisted — only a redacted URL
(host + path, query/fragment dropped, token-like path substrings masked), a
SHA-256 URL fingerprint, and a share-token fingerprint. The GET path is asserted
through the Prompt 02 read-only endpoint guard.
"""

from __future__ import annotations

import base64
import hashlib
import re
import uuid
from typing import Any, Literal, Optional
from urllib.parse import parse_qs, unquote, urlparse

from pydantic import BaseModel

from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.files_endpoint_guard import assert_files_request_allowed
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

GRAPH_SCOPES = ["Files.ReadWrite.All", "Sites.Read.All", "User.Read"]
_DRIVE_ITEM_SELECT = (
    "id,name,webUrl,size,file,folder,package,parentReference,sharepointIds,"
    "lastModifiedDateTime,createdDateTime,eTag,cTag"
)
# Token-like substrings to mask out of a redacted URL path (defensive).
_TOKEN_RE = re.compile(r"(?i)(guestaccess|tempauth|sharingtoken|[?&](e|d|at|token)=)[^/&]*")


def encode_sharing_url(url: str) -> str:
    """Encode a sharing URL to a Graph share token: ``u!`` + unpadded base64url."""
    b64 = base64.b64encode(url.encode("utf-8")).decode("ascii")
    return "u!" + b64.rstrip("=").replace("/", "_").replace("+", "-")


def fingerprint_url(url: str) -> str:
    """Stable, non-reversible fingerprint of a URL (never the raw URL)."""
    return "sha256:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def redact_graph_link_url(url: str) -> Optional[str]:
    """Return scheme://host/path (query + fragment dropped, token-like bits masked)."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    path = _TOKEN_RE.sub("[redacted]", parsed.path)
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _hostname(url: str) -> Optional[str]:
    return urlparse(url).netloc or None


def _normalized_path(url: str) -> Optional[str]:
    p = urlparse(url)
    if not p.path:
        return None
    return unquote(p.path).rstrip("/").lower() or "/"


def _server_relative_from_query(url: str) -> Optional[str]:
    """Extract the server-relative folder path from ``id`` / ``RootFolder`` query."""
    qs = parse_qs(urlparse(url).query)
    for key in ("id", "RootFolder", "rootfolder"):
        vals = qs.get(key)
        if vals and vals[0]:
            return unquote(vals[0]).rstrip("/")
    return None


class LinkResolutionResult(BaseModel):
    status: Literal["resolved", "pending", "unauthorized", "malformed", "unsupported", "error"]
    resolution_method: Literal[
        "shares_api", "me_drive_root", "source_registry_match", "url_query_parse", "none"
    ] = "none"
    item_kind: Literal["file", "folder", "package", "root_candidate", "unknown"] = "unknown"
    source_id: Optional[str] = None
    site_id: Optional[str] = None
    drive_id: Optional[str] = None
    drive_item_id: Optional[str] = None
    folder_item_id: Optional[str] = None
    parent_drive_id: Optional[str] = None
    parent_drive_item_id: Optional[str] = None
    list_id: Optional[str] = None
    list_item_id: Optional[str] = None
    web_url: Optional[str] = None
    name: Optional[str] = None
    redacted_url: Optional[str] = None
    hostname: Optional[str] = None
    normalized_path: Optional[str] = None
    url_fingerprint: Optional[str] = None
    share_token_fingerprint: Optional[str] = None
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


def _item_kind(item: dict[str, Any]) -> str:
    if isinstance(item.get("package"), dict):
        return "package"
    if isinstance(item.get("folder"), dict):
        return "folder"
    if isinstance(item.get("file"), dict):
        return "file"
    return "unknown"


class LinkResolver:
    """Read-only resolver: user link → canonical Graph IDs (no redemption)."""

    def __init__(
        self,
        http_client: Optional[GraphHttpClient] = None,
        store: Optional[ConstructionStore] = None,
    ) -> None:
        self._http = http_client
        self._store = store

    def resolve_link(
        self, url: str, *, dry_run: bool = True, source_id: Optional[str] = None
    ) -> LinkResolutionResult:
        redacted = redact_graph_link_url(url)
        result = LinkResolutionResult(
            status="malformed",
            source_id=source_id,
            redacted_url=redacted,
            hostname=_hostname(url),
            normalized_path=_normalized_path(url),
            url_fingerprint=fingerprint_url(url) if url else None,
        )
        # Malformed: not an http(s) URL with a host — never touch Graph.
        if redacted is None:
            result.error_redacted = "malformed_url: missing scheme or host"
            self._maybe_persist(result, dry_run)
            return result

        # Primary: Graph Shares API resolution (read-only; no redemption).
        if self._http is not None:
            encoded = encode_sharing_url(url)
            result.share_token_fingerprint = fingerprint_url(encoded)
            path = f"/shares/{encoded}/driveItem"
            assert_files_request_allowed("GET", path)  # guard: GET-only allowlisted
            try:
                item = self._http.get(
                    path, params={"$select": _DRIVE_ITEM_SELECT}, scopes=GRAPH_SCOPES
                )
                self._fill_from_drive_item(result, item)
                result.status = "resolved"
                result.resolution_method = "shares_api"
                self._maybe_persist(result, dry_run)
                return result
            except GraphHttpError as e:
                if e.status in (401, 403):
                    result.status = "unauthorized"
                    result.error_redacted = f"graph_{e.status}"
                    self._maybe_persist(result, dry_run)
                    return result
                if e.status != 404:
                    result.status = "error"
                    result.error_redacted = f"graph_{e.status}"
                    self._maybe_persist(result, dry_run)
                    return result
                # 404 → fall through to fallbacks.

        # Fallback (a): own-OneDrive-business-root link → /me/drive.
        if self._http is not None and self._is_onedrive_root_link(url):
            try:
                drive = self._http.get(
                    "/me/drive", params={"$select": "id,webUrl,driveType"}, scopes=GRAPH_SCOPES
                )
                result.drive_id = drive.get("id")
                result.web_url = drive.get("webUrl")
                result.item_kind = "root_candidate"
                result.status = "resolved" if result.drive_id else "pending"
                result.resolution_method = "me_drive_root"
                self._maybe_persist(result, dry_run)
                return result
            except GraphHttpError as e:
                result.status = "unauthorized" if e.status in (401, 403) else "error"
                result.error_redacted = f"graph_{e.status}"
                self._maybe_persist(result, dry_run)
                return result

        # Fallback (b): source-registry host/path match.
        matched = self._match_source_registry(url)
        if matched is not None:
            result.source_id = matched.source_key
            result.site_id = matched.site_id
            result.drive_id = matched.drive_id
            result.folder_item_id = matched.folder_item_id
            result.list_id = matched.list_id
            result.web_url = matched.folder_web_url or matched.site_url
            result.item_kind = "folder"
            result.status = "resolved" if matched.drive_id else "pending"
            result.resolution_method = "source_registry_match"
            self._maybe_persist(result, dry_run)
            return result

        # Fallback (c): URL-query parse only (partial; needs further resolution).
        srv_rel = _server_relative_from_query(url)
        result.status = "pending"
        result.resolution_method = "url_query_parse"
        result.error_redacted = (
            "resolved server-relative path only; no canonical IDs (provide --source-id or a share link)"
            if srv_rel
            else "no shares-api match and no registry/root mapping"
        )
        self._maybe_persist(result, dry_run)
        return result

    # -- helpers ------------------------------------------------------------

    def _fill_from_drive_item(self, result: LinkResolutionResult, item: dict[str, Any]) -> None:
        parent = (
            item.get("parentReference") if isinstance(item.get("parentReference"), dict) else {}
        )
        sp = item.get("sharepointIds") if isinstance(item.get("sharepointIds"), dict) else {}
        result.drive_item_id = item.get("id")
        result.name = item.get("name")
        result.web_url = item.get("webUrl")
        result.drive_id = (parent or {}).get("driveId")
        result.parent_drive_id = (parent or {}).get("driveId")
        result.parent_drive_item_id = (parent or {}).get("id")
        result.site_id = (sp or {}).get("siteId")
        result.list_id = (sp or {}).get("listId")
        result.list_item_id = (sp or {}).get("listItemId")
        kind = _item_kind(item)
        result.item_kind = kind  # type: ignore[assignment]
        if kind in ("folder", "package"):
            result.folder_item_id = item.get("id")

    @staticmethod
    def _is_onedrive_root_link(url: str) -> bool:
        host = (_hostname(url) or "").lower()
        path = (_normalized_path(url) or "").lower()
        if "-my.sharepoint.com" not in host:
            return False
        # Personal OneDrive root link (no specific item id beyond the personal root).
        return "/personal/" in path and ("/documents" in path or path.endswith("/documents"))

    def _match_source_registry(self, url: str):  # noqa: ANN202 - SourceLocation | None
        host = (_hostname(url) or "").lower()
        path = _normalized_path(url) or ""
        srv_rel = (_server_relative_from_query(url) or "").lower()
        try:
            registry = load_source_registry()
        except Exception:  # noqa: BLE001 - registry optional for resolution
            return None
        candidate = srv_rel or path
        # Sources whose registered site (host + site path) is a prefix of the link.
        site_matches = []
        for src in registry.sources:
            if not src.site_url:
                continue
            src_host = (urlparse(src.site_url).netloc or "").lower()
            src_path = (urlparse(src.site_url).path or "").rstrip("/").lower()
            if src_host and src_host == host and src_path and candidate.startswith(src_path):
                site_matches.append(src)
        if not site_matches:
            return None
        # Prefer a source whose project number appears in the link (disambiguates
        # multiple project folders under the same site). Folder names in URLs rarely
        # match the registry folder_path verbatim, so the project number is the
        # robust signal.
        for src in site_matches:
            pn = (src.project_number or "").lower()
            if pn and pn in candidate:
                return src
        # Otherwise only accept an unambiguous single site-level match.
        return site_matches[0] if len(site_matches) == 1 else None

    def _maybe_persist(self, result: LinkResolutionResult, dry_run: bool) -> None:
        if dry_run or self._store is None:
            return
        self._store.insert_link_resolution(
            resolution_id=str(uuid.uuid4()),
            source_id=result.source_id,
            redacted_url=result.redacted_url,
            hostname=result.hostname,
            normalized_path=result.normalized_path,
            url_fingerprint=result.url_fingerprint,
            share_token_fingerprint=result.share_token_fingerprint,
            resolution_method=result.resolution_method,
            status=result.status,
            site_id=result.site_id,
            drive_id=result.drive_id,
            drive_item_id=result.drive_item_id,
            folder_item_id=result.folder_item_id,
            parent_drive_id=result.parent_drive_id,
            parent_drive_item_id=result.parent_drive_item_id,
            list_id=result.list_id,
            list_item_id=result.list_item_id,
            web_url=result.web_url,
            name=result.name,
            item_kind=result.item_kind,
            error_redacted=result.error_redacted,
        )
