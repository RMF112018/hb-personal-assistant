"""Read-only Microsoft Graph delta crawler for construction-agent sources.

Iterates `/drives/{driveId}/root/delta` with `@odata.nextLink` pagination,
records the final `@odata.deltaLink`, and (in apply mode) persists
**metadata-only** drive-item snapshots plus a crawl receipt to SQLite.

Guardrails:
- No source-document body, text, or excerpt is ever read or stored.
- Dry-run never writes to SQLite.
- Apply writes inventory + token + receipt in a single transaction per call.
- Items with a `deleted` field are marked status='deleted' in inventory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

from .resolver import GRAPH_SCOPES, _redact_item_preview


class CrawlReceipt(BaseModel):
    run_id: str
    source_key: str
    drive_id: Optional[str]
    mode: str  # "dry_run" | "apply"
    status: str  # "ok" | "auth_required" | "unresolved" | "failed" | "skipped"
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

    model_config = {"extra": "forbid"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConstructionDeltaCrawler:
    """Crawls a single source's drive delta feed."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: ConstructionStore,
    ) -> None:
        self._http = http_client
        self._store = store

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

        if drive_id is None:
            resolution = self._store.get_resolution(source_key)
            drive_id = (resolution or {}).get("drive_id")

        if not drive_id:
            receipt = CrawlReceipt(
                run_id=run_id,
                source_key=source_key,
                drive_id=None,
                mode=mode,
                status="unresolved",
                started_at=started_at,
                finished_at=_utc_now(),
                error_redacted="no drive_id resolved; run `graph sources resolve --apply` first",
            )
            if not dry_run:
                self._persist_receipt(receipt)
            return receipt

        existing_token = self._store.get_delta_token(source_key) if not dry_run else None
        prior_delta_link = (existing_token or {}).get("delta_link")

        first_path = prior_delta_link or f"/drives/{drive_id}/root/delta"

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
                page = self._http.get(path, scopes=GRAPH_SCOPES)
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
        )
        if not dry_run:
            self._persist_receipt(receipt)
        return receipt

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
