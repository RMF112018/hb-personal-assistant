"""Service that builds manifest/receipt models from construction store state."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.delta_crawler import CrawlReceipt
from hb_assistant.construction.store import ConstructionStore

from .models import (
    ProcessingReceipt,
    SourceManifest,
    SourceManifestEntry,
    SyncReceipt,
)

GUARDRAILS_DEFAULT: dict[str, str] = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": "true",
    "delta_token_storage": "sqlite",
    "markdown_role": "projection_only",
    "sqlite_authoritative": "true",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def delta_link_fingerprint(delta_link: Optional[str]) -> Optional[str]:
    """Return a stable, non-reversible fingerprint of the delta link.

    The full delta_link must never appear in Markdown — only this fingerprint
    is rendered. SQLite remains authoritative for the actual token.
    """

    if not delta_link:
        return None
    digest = hashlib.sha256(delta_link.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


class ManifestService:
    """Build manifest/receipt projections from ConstructionStore state."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store

    def build_source_manifest(
        self,
        source: SourceLocation,
        *,
        run_id: str,
        sample_size: int = 20,
    ) -> SourceManifest:
        resolution = self._store.get_resolution(source.source_key) or {}
        token = self._store.get_delta_token(source.source_key) or {}
        counts = self._store.count_inventory(source.source_key)
        sample_rows = self._store.list_inventory_changed_since(
            source.source_key, since_iso="1970-01-01T00:00:00+00:00", limit=sample_size
        )

        sample_entries = [
            SourceManifestEntry(
                item_id=row["item_id"],
                name=row.get("name"),
                web_url=row.get("web_url"),
                parent_path=row.get("parent_path"),
                size_bytes=row.get("size_bytes"),
                is_folder=bool(row.get("is_folder")),
                status=row.get("status", "active"),
                last_modified=row.get("last_modified"),
            )
            for row in sample_rows
        ]

        return SourceManifest(
            source_key=source.source_key,
            project_key=source.project_key,
            kind=source.kind,
            display_name=source.display_name,
            resolution_status=resolution.get("resolution_status", source.resolution_status),
            drive_id=resolution.get("drive_id"),
            web_url=resolution.get("web_url") or source.site_url,
            generated_at=_utc_now(),
            run_id=run_id,
            item_counts=counts,
            sample_entries=sample_entries,
            sample_size_cap=sample_size,
            delta_link_fingerprint=delta_link_fingerprint(token.get("delta_link")),
            last_sync_at=token.get("last_sync_at"),
            guardrails=dict(GUARDRAILS_DEFAULT),
        )

    def build_sync_receipt(self, crawl_receipt: CrawlReceipt) -> SyncReceipt:
        return SyncReceipt(
            run_id=crawl_receipt.run_id,
            source_key=crawl_receipt.source_key,
            mode=crawl_receipt.mode,
            status=crawl_receipt.status,
            started_at=crawl_receipt.started_at,
            finished_at=crawl_receipt.finished_at,
            pages_seen=crawl_receipt.pages_seen,
            items_seen=crawl_receipt.items_seen,
            items_new=crawl_receipt.items_new,
            items_updated=crawl_receipt.items_updated,
            items_deleted=crawl_receipt.items_deleted,
            delta_link_recorded=crawl_receipt.delta_link_recorded,
            error_redacted=crawl_receipt.error_redacted,
            guardrails=dict(GUARDRAILS_DEFAULT),
        )

    def build_sync_receipt_from_store(
        self,
        source_key: str,
        run_id: str,
        started_at: str,
    ) -> SyncReceipt:
        """Project a SyncReceipt from the most recent stored crawl receipt.

        Used when no Graph token is available — yields ``status='projected'``
        carrying the last known per-source counts so downstream Markdown
        previews remain accurate.
        """

        receipts = self._store.list_recent_receipts(source_key, limit=1)
        if not receipts:
            return SyncReceipt(
                run_id=run_id,
                source_key=source_key,
                mode="dry_run",
                status="projected",
                started_at=started_at,
                finished_at=_utc_now(),
                guardrails=dict(GUARDRAILS_DEFAULT),
                error_redacted="no prior crawl receipt available",
            )
        latest = receipts[0]
        return SyncReceipt(
            run_id=run_id,
            source_key=source_key,
            mode="dry_run",
            status="projected",
            started_at=started_at,
            finished_at=_utc_now(),
            pages_seen=latest["pages_seen"],
            items_seen=latest["items_seen"],
            items_new=latest["items_new"],
            items_updated=latest["items_updated"],
            items_deleted=latest["items_deleted"],
            delta_link_recorded=bool(latest["delta_link_recorded"]),
            error_redacted=latest.get("error_redacted"),
            guardrails=dict(GUARDRAILS_DEFAULT),
        )

    def build_processing_receipt(
        self,
        run_id: str,
        mode: str,
        started_at: str,
        finished_at: str,
        per_source: list[SyncReceipt],
    ) -> ProcessingReceipt:
        totals = {
            "pages_seen": sum(r.pages_seen for r in per_source),
            "items_seen": sum(r.items_seen for r in per_source),
            "items_new": sum(r.items_new for r in per_source),
            "items_updated": sum(r.items_updated for r in per_source),
            "items_deleted": sum(r.items_deleted for r in per_source),
        }
        errors = [
            f"{r.source_key}: {r.error_redacted}"
            for r in per_source
            if r.error_redacted
        ]
        return ProcessingReceipt(
            run_id=run_id,
            mode=mode,
            started_at=started_at,
            finished_at=finished_at,
            source_count=len(per_source),
            per_source=per_source,
            totals=totals,
            error_summary=errors,
            guardrails=dict(GUARDRAILS_DEFAULT),
        )
