"""Service that builds manifest/receipt models from construction store state."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable, Optional

from hb_assistant.construction.baseline import (
    BaselineComparison,
    compute_baseline_comparison,
)
from hb_assistant.construction.config import SourceLocation, SourceRegistry
from hb_assistant.construction.graph.delta_crawler import CrawlReceipt
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection

from .canonical_adapter import (
    CanonicalDocumentCardInput,
    read_canonical_document_card_input,
)
from .models import (
    DocumentCard,
    ProcessingReceipt,
    ProjectCard,
    RegistryOverview,
    ReviewRequiredItem,
    ReviewRequiredNote,
    SourceManifest,
    SourceManifestEntry,
    SyncReceipt,
)


class DocumentCardPolicyError(ValueError):
    """Raised when a document card is requested without an explicit policy_reason."""

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

    def build_baseline_comparison(
        self,
        registry: SourceRegistry,
        source_key: str,
        *,
        tolerance_pct: float = 5.0,
    ) -> BaselineComparison:
        """Look up ``source_key`` in the registry and compare historic vs current counts."""
        source = next(
            (s for s in registry.sources if s.source_key == source_key),
            None,
        )
        if source is None:
            raise KeyError(
                f"source_key {source_key!r} not present in registry; "
                "cannot build baseline comparison"
            )
        return compute_baseline_comparison(
            source, self._store, tolerance_pct=tolerance_pct
        )

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

    def build_registry_overview(self, registry: SourceRegistry) -> RegistryOverview:
        projects = [
            {
                "project_key": p.project_key,
                "display_name": p.display_name,
                "status": p.status,
                "primary_company": p.primary_company,
            }
            for p in registry.projects
        ]
        sources_by_project: dict[str, list[str]] = {p.project_key: [] for p in registry.projects}
        unresolved: list[str] = []
        for src in registry.sources:
            key = src.project_key or "_unassigned_"
            sources_by_project.setdefault(key, []).append(src.source_key)
            resolution = self._store.get_resolution(src.source_key) or {}
            if resolution.get("resolution_status", src.resolution_status) != "resolved":
                unresolved.append(src.source_key)
        return RegistryOverview(
            generated_at=_utc_now(),
            project_count=len(registry.projects),
            source_count=len(registry.sources),
            projects=projects,
            sources_by_project=sources_by_project,
            unresolved_sources=sorted(unresolved),
            guardrails=dict(GUARDRAILS_DEFAULT),
        )

    def build_project_card(
        self, registry: SourceRegistry, project_key: str,
    ) -> ProjectCard:
        project = next((p for p in registry.projects if p.project_key == project_key), None)
        if project is None:
            raise ValueError(f"unknown project_key: {project_key!r}")
        project_sources = [s for s in registry.sources if s.project_key == project_key]
        totals: dict[str, int] = {}
        last_sync_at: str | None = None
        for src in project_sources:
            counts = self._store.count_inventory(src.source_key)
            for status, n in counts.items():
                totals[status] = totals.get(status, 0) + n
            token = self._store.get_delta_token(src.source_key) or {}
            ts = token.get("last_sync_at")
            if ts and (last_sync_at is None or ts > last_sync_at):
                last_sync_at = ts

        # Prompt 12 continuation: include Procore sync-state summary in
        # the construction project-card totals projection for pilot projects.
        procore_entities = 0
        procore_review_required = 0
        procore_watermark_count = 0
        procore_last_watermark_fp: str | None = None
        try:
            conn = get_connection(getattr(self._store, "_db_path", None))
            row = conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN review_required = 1 THEN 1 ELSE 0 END) AS rr
                FROM procore_synced_entities
                WHERE source_project_key = ?
                """,
                (project_key,),
            ).fetchone()
            if row is not None:
                procore_entities = int(row["n"] or 0)
                procore_review_required = int(row["rr"] or 0)

            wm = conn.execute(
                """
                SELECT COUNT(*) AS n, MAX(last_successful_watermark) AS latest
                FROM procore_sync_watermarks
                WHERE project_key = ?
                """,
                (project_key,),
            ).fetchone()
            if wm is not None:
                procore_watermark_count = int(wm["n"] or 0)
                latest = wm["latest"]
                if latest:
                    digest = hashlib.sha256(str(latest).encode("utf-8")).hexdigest()
                    procore_last_watermark_fp = f"sha256:{digest[:12]}"
        except Exception:
            # Keep construction manifests resilient when procore_* tables are
            # absent on a fresh local checkout.
            pass

        if procore_entities > 0:
            totals["procore_entities_total"] = procore_entities
        if procore_review_required > 0:
            totals["procore_review_required_total"] = procore_review_required
        if procore_watermark_count > 0:
            totals["procore_watermark_count"] = procore_watermark_count
        project_guardrails = dict(GUARDRAILS_DEFAULT)
        if procore_last_watermark_fp:
            project_guardrails["procore_last_watermark_fp"] = procore_last_watermark_fp

        return ProjectCard(
            project_key=project.project_key,
            display_name=project.display_name,
            status=project.status,
            primary_company=project.primary_company,
            source_count=len(project_sources),
            source_keys=[s.source_key for s in project_sources],
            totals=totals,
            last_sync_at=last_sync_at,
            generated_at=_utc_now(),
            guardrails=project_guardrails,
        )

    def build_review_required_note(
        self,
        items: Iterable[ReviewRequiredItem] | None = None,
    ) -> ReviewRequiredNote:
        """Build a review-required note.

        When ``items`` is ``None``, defaults to pulling every open row from the
        review queue in the bound :class:`ConstructionStore` (V3 schema) and
        projecting them to :class:`ReviewRequiredItem`. Pass an explicit
        ``items`` iterable (including ``[]``) to bypass the store pull.
        """

        if items is None:
            rows = self._store.list_review_queue(status="open")
            items = [
                ReviewRequiredItem(
                    item_id=row["item_id"],
                    source_key=row["source_key"],
                    project_key=row.get("project_key"),
                    name=row.get("name"),
                    reason=row["reason"],
                    suggested_action=row.get("suggested_action"),
                    classification_label=row.get("classification_label"),
                    sensitivity=row.get("sensitivity"),
                )
                for row in rows
            ]
        return ReviewRequiredNote(
            generated_at=_utc_now(),
            items=list(items),
            guardrails=dict(GUARDRAILS_DEFAULT),
        )

    def build_document_card(
        self,
        *,
        source: SourceLocation,
        item_id: str,
        policy_reason: str,
    ) -> DocumentCard:
        """Emit a single per-document card. Requires a non-empty policy_reason."""

        if not policy_reason or not policy_reason.strip():
            raise DocumentCardPolicyError(
                "DocumentCard requires an explicit non-empty policy_reason "
                "(per-document cards are not auto-generated)."
            )
        rows = self._store.list_inventory_changed_since(
            source.source_key, since_iso="1970-01-01T00:00:00+00:00", limit=1000,
        )
        match = next((r for r in rows if r.get("item_id") == item_id), None)
        if match is None:
            raise ValueError(
                f"item_id {item_id!r} not found in inventory for source {source.source_key!r}"
            )
        return DocumentCard(
            source_key=source.source_key,
            # V5 canonical source_id is identical to the registry source_key
            # under the current projection mapping; we still plumb it as a
            # distinct frontmatter field so the canonical read path can
            # diverge later without a model change.
            source_id=source.source_key,
            project_key=source.project_key,
            item_id=item_id,
            name=match.get("name"),
            web_url=match.get("web_url"),
            parent_path=match.get("parent_path"),
            size_bytes=match.get("size_bytes"),
            is_folder=bool(match.get("is_folder")),
            last_modified=match.get("last_modified"),
            status=match.get("status", "active"),
            policy_reason=policy_reason.strip(),
            generated_at=_utc_now(),
            guardrails=dict(GUARDRAILS_DEFAULT),
        )

    def build_document_card_from_source_id(
        self,
        *,
        source_id: str,
        item_id: str,
        policy_reason: str,
    ) -> DocumentCard:
        """Canonical V5 read-path: emit a per-document card keyed by the
        V5 ``construction_source_locations.source_id`` rather than a V2
        registry :class:`SourceLocation`.

        Drive items are read via
        :func:`hb_assistant.construction.drive_item_bridge.read_drive_items_unified`
        (V5-wins precedence) and adapted to the inventory-row dict shape
        that the existing renderer pathway consumes — every redaction
        and guardrail behavior inherits unchanged.

        Fails closed: raises :class:`CanonicalSourceNotFound` if
        ``source_id`` is not present in ``construction_source_locations``
        and :class:`DocumentCardPolicyError` if ``policy_reason`` is
        empty.
        """

        if not policy_reason or not policy_reason.strip():
            raise DocumentCardPolicyError(
                "DocumentCard requires an explicit non-empty policy_reason "
                "(per-document cards are not auto-generated)."
            )
        bundle: CanonicalDocumentCardInput = read_canonical_document_card_input(
            self._store, source_id=source_id,
        )
        match = next(
            (r for r in bundle.rows if r.get("item_id") == item_id), None,
        )
        if match is None:
            raise ValueError(
                f"item_id {item_id!r} not found in canonical drive items "
                f"for source_id {source_id!r}"
            )
        return DocumentCard(
            source_key=bundle.ref.source_key,
            source_id=bundle.ref.source_id,
            project_key=bundle.ref.project_key,
            item_id=item_id,
            name=match.get("name"),
            web_url=match.get("web_url"),
            parent_path=match.get("parent_path"),
            size_bytes=match.get("size_bytes"),
            is_folder=bool(match.get("is_folder")),
            last_modified=match.get("last_modified"),
            status=match.get("status", "active"),
            policy_reason=policy_reason.strip(),
            generated_at=_utc_now(),
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
