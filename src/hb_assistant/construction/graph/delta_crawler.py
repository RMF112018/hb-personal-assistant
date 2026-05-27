"""Read-only Microsoft Graph delta crawler for construction-agent sources.

Selects the right delta endpoint based on the source's canonical scope:

- ``sharepoint_project_drive_folder`` + ``folder_item_id``
                                                    → ``/drives/{drive_id}/items/{folder_item_id}/delta``
                                                    (folder-scoped delta, ``endpoint_kind="folder_scoped"``).
- ``sharepoint_project_drive_folder`` without folder_item_id but with drive_id
                                                    → ``/drives/{drive_id}/root/delta``
                                                    (``endpoint_kind="drive_root_fallback"``).
- ``sharepoint_site``, ``sharepoint_library`` (legacy)
                                                    → ``/drives/{drive_id}/root/delta``
                                                    (``endpoint_kind="drive_root"``).
- ``onedrive_personal`` (legacy), ``onedrive_personal_root``
                                                    → ``/drives/{drive_id}/root/delta`` if a
                                                    drive_id was resolved, else
                                                    ``/me/drive/root/delta``
                                                    (``endpoint_kind="me_drive_delta"``).
- ``onedrive_business_root``                        → ``/me/drive/root/delta`` (delegated
                                                    business token resolves to /me/drive on
                                                    Graph).
- ``onedrive_shared`` (legacy), ``onedrive_shared_library`` + drive_id
                                                    → ``/drives/{drive_id}/root/delta``.
- ``sharepoint_site_page``                          → no delta endpoint; receipt exits
                                                    ``status="skipped_unsupported_scope"``.

Guardrails:
- No source-document body, text, or excerpt is ever read or stored.
- Dry-run never writes to SQLite.
- Apply writes inventory + token + receipt in a single transaction per call.
- Items with a ``deleted`` field are marked status='deleted' in inventory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.baseline import (
    BaselineComparison,
    compute_baseline_comparison,
)
from hb_assistant.construction.config import SourceLocation, load_source_registry
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

from .resolver import GRAPH_SCOPES_DRIVE, _redact_item_preview


class CrawlReceipt(BaseModel):
    run_id: str
    source_key: str
    drive_id: Optional[str]
    mode: str  # "dry_run" | "apply"
    status: str  # "ok" | "auth_required" | "unresolved" | "failed" | "skipped" | "skipped_unsupported_scope"
    started_at: str
    finished_at: Optional[str] = None
    pages_seen: int = 0
    items_seen: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_deleted: int = 0
    delta_link_recorded: bool = False
    sample_items: list[dict[str, Any]] = []
    error_redacted: Optional[str] = None
    scope: Optional[str] = None
    endpoint_kind: Optional[str] = None
    folder_item_id: Optional[str] = None
    baseline_comparison: Optional[BaselineComparison] = None

    model_config = {"extra": "forbid"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _select_delta_endpoint(
    source: SourceLocation,
) -> tuple[Optional[str], str, Optional[str], Optional[str]]:
    """Return ``(endpoint_path, endpoint_kind, drive_id_used, folder_item_id_used)``.

    ``endpoint_path`` is ``None`` for scopes that don't support delta
    (``sharepoint_site_page``); the caller emits a skipped-receipt in that
    case. ``drive_id_used`` may be ``None`` when the crawler must look up a
    resolved drive_id via the store (e.g., legacy ``sharepoint_site``).
    """
    kind = source.kind
    drive_id = source.drive_id
    folder_item_id = source.folder_item_id

    if kind == "sharepoint_site_page":
        return (None, "site_page_unsupported", None, None)

    if kind == "sharepoint_project_drive_folder":
        if drive_id and folder_item_id:
            return (
                f"/drives/{drive_id}/items/{folder_item_id}/delta",
                "folder_scoped",
                drive_id,
                folder_item_id,
            )
        if drive_id:
            return (
                f"/drives/{drive_id}/root/delta",
                "drive_root_fallback",
                drive_id,
                None,
            )
        # No drive_id yet — caller will detect unresolved.
        return (None, "drive_root_fallback", None, None)

    if kind in ("sharepoint_site", "sharepoint_library"):
        if drive_id:
            return (f"/drives/{drive_id}/root/delta", "drive_root", drive_id, None)
        return (None, "drive_root", None, None)

    if kind in ("onedrive_personal", "onedrive_personal_root"):
        if drive_id:
            return (
                f"/drives/{drive_id}/root/delta",
                "drive_root",
                drive_id,
                None,
            )
        return ("/me/drive/root/delta", "me_drive_delta", None, None)

    if kind == "onedrive_business_root":
        return ("/me/drive/root/delta", "me_drive_delta", drive_id, None)

    if kind in ("onedrive_shared", "onedrive_shared_library"):
        if drive_id:
            return (f"/drives/{drive_id}/root/delta", "drive_root", drive_id, None)
        return (None, "drive_root", None, None)

    return (None, "unknown_scope", None, None)


class ConstructionDeltaCrawler:
    """Crawls a single source's drive delta feed."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: ConstructionStore,
    ) -> None:
        self._http = http_client
        self._store = store

    def _lookup_source(self, source_key: str) -> Optional[SourceLocation]:
        try:
            registry = load_source_registry()
        except Exception:  # noqa: BLE001
            return None
        for src in registry.sources:
            if src.source_key == source_key:
                return src
        return None

    def crawl(
        self,
        *,
        source_key: str,
        drive_id: Optional[str] = None,
        dry_run: bool = True,
        max_pages: int = 50,
    ) -> CrawlReceipt:
        run_id = str(uuid.uuid4())
        mode = "dry_run" if dry_run else "apply"
        started_at = _utc_now()

        source = self._lookup_source(source_key)

        # Site-page scope: no delta crawl available; short-circuit cleanly.
        if source is not None and source.kind == "sharepoint_site_page":
            receipt = CrawlReceipt(
                run_id=run_id,
                source_key=source_key,
                drive_id=None,
                mode=mode,
                status="skipped_unsupported_scope",
                started_at=started_at,
                finished_at=_utc_now(),
                scope=source.kind,
                endpoint_kind="site_page_unsupported",
                error_redacted=(
                    "sharepoint_site_page sources are not delta-crawled; "
                    "a dedicated page crawler is required"
                ),
            )
            if not dry_run:
                self._persist_receipt(receipt)
            return receipt

        endpoint_path: Optional[str] = None
        endpoint_kind: str = "drive_root"
        folder_item_id_used: Optional[str] = None
        scope: Optional[str] = source.kind if source else None

        if source is not None:
            (
                endpoint_path,
                endpoint_kind,
                resolved_drive_id,
                folder_item_id_used,
            ) = _select_delta_endpoint(source)
            if drive_id is None and resolved_drive_id is not None:
                drive_id = resolved_drive_id

        # Fall back to V2 store resolution if we still don't have a drive_id.
        if drive_id is None and endpoint_path is None:
            resolution = self._store.get_resolution(source_key)
            drive_id = (resolution or {}).get("drive_id")
            if drive_id:
                endpoint_path = f"/drives/{drive_id}/root/delta"
                endpoint_kind = "drive_root"

        if not endpoint_path:
            receipt = CrawlReceipt(
                run_id=run_id,
                source_key=source_key,
                drive_id=None,
                mode=mode,
                status="unresolved",
                started_at=started_at,
                finished_at=_utc_now(),
                scope=scope,
                endpoint_kind=endpoint_kind,
                error_redacted="no drive_id resolved; run `graph sources resolve --apply` first",
            )
            if not dry_run:
                self._persist_receipt(receipt)
            return receipt

        existing_token = self._store.get_delta_token(source_key) if not dry_run else None
        prior_delta_link = (existing_token or {}).get("delta_link")

        first_path = prior_delta_link or endpoint_path

        pages_seen = 0
        items_seen = 0
        items_new = 0
        items_updated = 0
        items_deleted = 0
        sample_items: list[dict[str, Any]] = []
        delta_link: Optional[str] = None
        path: str = first_path

        try:
            while pages_seen < max_pages:
                page = self._http.get(path, scopes=GRAPH_SCOPES_DRIVE)
                pages_seen += 1
                for item in page.get("value", []):
                    items_seen += 1
                    if len(sample_items) < 5:
                        sample_items.append(_redact_item_preview(item))
                    if not dry_run:
                        new, updated, deleted = self._apply_item(source_key, drive_id, item)
                        items_new += new
                        items_updated += updated
                        items_deleted += deleted
                next_link = page.get("@odata.nextLink")
                delta_link = page.get("@odata.deltaLink") or delta_link
                if not next_link:
                    break
                path = next_link
        except GraphHttpError as e:
            receipt = CrawlReceipt(
                run_id=run_id,
                source_key=source_key,
                drive_id=drive_id,
                mode=mode,
                status="failed",
                started_at=started_at,
                finished_at=_utc_now(),
                pages_seen=pages_seen,
                items_seen=items_seen,
                items_new=items_new,
                items_updated=items_updated,
                items_deleted=items_deleted,
                delta_link_recorded=False,
                sample_items=sample_items,
                error_redacted=f"graph_{e.status}: {e.message[:120]}",
                scope=scope,
                endpoint_kind=endpoint_kind,
                folder_item_id=folder_item_id_used,
            )
            if not dry_run:
                self._persist_receipt(receipt)
            return receipt

        delta_link_recorded = False
        if not dry_run and delta_link is not None:
            self._store.set_delta_token(
                source_key=source_key,
                drive_id=drive_id,
                delta_link=delta_link,
                page_count=pages_seen,
                last_status="ok",
            )
            delta_link_recorded = True

        baseline_comparison: Optional[BaselineComparison] = None
        if source is not None and source.baseline is not None:
            baseline_comparison = compute_baseline_comparison(source, self._store)
            if not dry_run:
                self._persist_baseline_processing_receipt(
                    source_key=source_key,
                    run_id=run_id,
                    comparison=baseline_comparison,
                )

        receipt = CrawlReceipt(
            run_id=run_id,
            source_key=source_key,
            drive_id=drive_id,
            mode=mode,
            status="ok",
            started_at=started_at,
            finished_at=_utc_now(),
            pages_seen=pages_seen,
            items_seen=items_seen,
            items_new=items_new,
            items_updated=items_updated,
            items_deleted=items_deleted,
            delta_link_recorded=delta_link_recorded,
            sample_items=sample_items,
            scope=scope,
            endpoint_kind=endpoint_kind,
            folder_item_id=folder_item_id_used,
            baseline_comparison=baseline_comparison,
        )
        if not dry_run:
            self._persist_receipt(receipt)
        return receipt

    def _persist_baseline_processing_receipt(
        self,
        *,
        source_key: str,
        run_id: str,
        comparison: BaselineComparison,
    ) -> None:
        """Persist a baseline-comparison row to construction_processing_receipts.

        Receipt id is ``{run_id}:baseline_comparison`` so multiple comparisons
        from distinct crawl runs do not collide on the receipt primary key.
        ``detail`` carries the full :class:`BaselineComparison` JSON.
        """
        self._store.insert_processing_receipt(
            receipt_id=f"{run_id}:baseline_comparison",
            source_id=source_key,
            operation="baseline_comparison",
            status=comparison.status,
            detail=comparison.model_dump(mode="json"),
        )

    def _apply_item(
        self,
        source_key: str,
        drive_id: str,
        item: dict[str, Any],
    ) -> tuple[int, int, int]:
        """Persist a single delta item. Returns (new, updated, deleted) counts."""
        item_id = item.get("id")
        if not item_id:
            return (0, 0, 0)

        if item.get("deleted") is not None:
            matched = self._store.mark_inventory_deleted(
                source_key=source_key,
                item_id=item_id,
            )
            return (0, 0, 1 if matched else 0)

        parent_ref = item.get("parentReference") or {}
        outcome = self._store.upsert_inventory_item(
            source_key=source_key,
            drive_id=drive_id,
            item_id=item_id,
            name=item.get("name"),
            web_url=item.get("webUrl"),
            parent_path=parent_ref.get("path"),
            size_bytes=item.get("size"),
            is_folder=bool(item.get("folder")),
            last_modified=item.get("lastModifiedDateTime"),
            etag=item.get("eTag"),
        )
        if outcome == "new":
            return (1, 0, 0)
        return (0, 1, 0)

    def _persist_receipt(self, receipt: CrawlReceipt) -> None:
        self._store.insert_crawl_receipt(
            run_id=receipt.run_id,
            source_key=receipt.source_key,
            mode=receipt.mode,
            started_at=receipt.started_at,
            finished_at=receipt.finished_at,
            pages_seen=receipt.pages_seen,
            items_seen=receipt.items_seen,
            items_new=receipt.items_new,
            items_updated=receipt.items_updated,
            items_deleted=receipt.items_deleted,
            delta_link_recorded=receipt.delta_link_recorded,
            status=receipt.status,
            error_redacted=receipt.error_redacted,
        )
