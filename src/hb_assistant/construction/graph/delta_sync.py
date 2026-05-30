"""Phase 06A — hardened incremental delta synchronization into the V5 canonical layer.

Follows ``@odata.nextLink`` to exhaustion, captures the final ``@odata.deltaLink``,
persists it to SQLite **only** (`construction_source_sync_state.delta_link`), handles
the ``deleted`` facet, and recovers from a stale token / ``410 Gone`` by marking the
source ``requires_rebaseline`` (never silently discarding state).

Raw-link redaction is the headline guardrail: the raw delta/next links — and a stored
prior delta link (the incremental start path) — are token-bearing and are written to
SQLite only. The report/JSON/evidence carry **only** ``delta_link_fingerprint``
(``sha256:<12>``); the report ``endpoint`` is the logical delta template plus a
``started_from`` flag, never the raw deltaLink URL.

Reuses the Prompt 06 ``normalize_drive_item`` + ``upsert_drive_item`` (deleted facet
handled) for the rich V5 rows. Metadata only; no content; ``@microsoft.graph.downloadUrl``
is never touched. The V2 ``ConstructionDeltaCrawler`` is left unchanged (parallel path).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.drive_item_indexer import normalize_drive_item
from hb_assistant.construction.graph.resolver import ConstructionGraphResolver
from hb_assistant.construction.manifests.service import delta_link_fingerprint
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.files_endpoint_guard import assert_files_request_allowed
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

GRAPH_SCOPES = ["Files.ReadWrite.All", "User.Read"]
_DEFAULT_MAX_PAGES = 50
_DEFAULT_MAX_ITEMS = 5000
_ME_DRIVE_KINDS = {"onedrive_business_root", "onedrive_personal_root", "onedrive_personal"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeltaSyncReport(BaseModel):
    run_id: str
    source_id: str
    kind: str
    scope: Optional[str] = None
    mode: str  # dry_run | apply
    endpoint: Optional[str] = None  # LOGICAL delta template (never the raw deltaLink)
    started_from: str = "initial"  # initial | stored_delta
    status: str  # ok | requires_rebaseline | pending | unsupported | error
    pages_seen: int = 0
    items_seen: int = 0
    items_changed: int = 0
    items_deleted: int = 0
    items_persisted: int = 0
    delta_link_fingerprint: Optional[str] = None  # ONLY fingerprint; never the raw link
    delta_link_recorded: bool = False
    truncated_by: str = "none"  # none | max_pages | max_items
    note: Optional[str] = None
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class DeltaSync:
    """Hardened incremental delta sync → V5 canonical sync state + drive items."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: Optional[ConstructionStore] = None,
    ) -> None:
        self._http = http_client
        self._store = store
        self._resolver = ConstructionGraphResolver(http_client)

    def _logical_endpoint(self, res: Any) -> Optional[str]:
        if res.drive_id and res.folder_item_id:
            return f"/drives/{res.drive_id}/items/{res.folder_item_id}/delta"
        if res.drive_id:
            return f"/drives/{res.drive_id}/root/delta"
        if res.kind in _ME_DRIVE_KINDS:
            return "/me/drive/root/delta"
        return None

    def sync(
        self,
        source: SourceLocation,
        *,
        dry_run: bool = True,
        max_pages: int = _DEFAULT_MAX_PAGES,
        max_items: int = _DEFAULT_MAX_ITEMS,
    ) -> DeltaSyncReport:
        run_id = str(uuid.uuid4())
        res = self._resolver.resolve(source)
        scope = res.scope or source.kind
        base: dict[str, Any] = {
            "run_id": run_id,
            "source_id": source.source_key,
            "kind": source.kind,
            "scope": scope,
            "mode": "dry_run" if dry_run else "apply",
        }
        if res.status == "unsupported":
            return DeltaSyncReport(status="unsupported", **base)
        logical_endpoint = self._logical_endpoint(res)
        if logical_endpoint is None:
            return DeltaSyncReport(
                status="pending",
                note=res.error_redacted or "drive_id unresolved; cannot delta-sync",
                **base,
            )

        # Read prior sync state (raw delta_link is the incremental start path; it is
        # token-bearing and is NEVER echoed — used only as the request path).
        prior = self._store.get_source_sync_state(source.source_key) if self._store else None
        prior_delta_link = (prior or {}).get("delta_link")
        started_from = "stored_delta" if prior_delta_link else "initial"
        path: Optional[str] = prior_delta_link or logical_endpoint
        params: Optional[dict[str, Any]] = None if prior_delta_link else {"$top": "200"}

        pages_seen = items_seen = changed = deleted = persisted = 0
        truncated_by = "none"
        new_delta_link: Optional[str] = None
        done = False
        try:
            while path is not None and not done:
                if pages_seen >= max_pages:
                    truncated_by = "max_pages"
                    break
                assert_files_request_allowed("GET", path)  # normalized; token stripped
                data = self._http.get(path, params=params, scopes=GRAPH_SCOPES)
                pages_seen += 1
                for item in data.get("value", []) or []:
                    if items_seen >= max_items:
                        truncated_by = "max_items"
                        done = True
                        break
                    items_seen += 1
                    kwargs = normalize_drive_item(source.source_key, res.drive_id or "", item)
                    if not kwargs.get("drive_item_id"):
                        continue
                    if kwargs.get("deleted"):
                        deleted += 1
                    else:
                        changed += 1
                    if not dry_run and self._store is not None:
                        self._store.upsert_drive_item(**kwargs)
                        persisted += 1
                if done:
                    break
                # Capture the rolling deltaLink; advance via nextLink.
                new_delta_link = data.get("@odata.deltaLink") or new_delta_link
                next_link = data.get("@odata.nextLink")
                if not next_link:
                    break
                path = next_link  # absolute continuation (token-bearing; never echoed)
                params = None
        except GraphHttpError as e:
            if e.status == 410:
                return self._finish_rebaseline(base, logical_endpoint, started_from, dry_run)
            report = DeltaSyncReport(
                status="error",
                endpoint=logical_endpoint,
                started_from=started_from,
                pages_seen=pages_seen,
                items_seen=items_seen,
                items_changed=changed,
                items_deleted=deleted,
                error_redacted=f"graph_{e.status}",
                **base,
            )
            self._persist_attempt(report, delta_link=None, dry_run=dry_run, res=res)
            return report

        # On truncation no final deltaLink is available; preserve the prior token so
        # the next run resumes rather than re-baselining (status="partial").
        effective_delta = new_delta_link or prior_delta_link
        status = "ok" if new_delta_link else ("partial" if truncated_by != "none" else "ok")
        report = DeltaSyncReport(
            status=status,
            endpoint=logical_endpoint,
            started_from=started_from,
            pages_seen=pages_seen,
            items_seen=items_seen,
            items_changed=changed,
            items_deleted=deleted,
            items_persisted=persisted,
            delta_link_fingerprint=delta_link_fingerprint(effective_delta),
            delta_link_recorded=bool(new_delta_link) and not dry_run,
            truncated_by=truncated_by,
            **base,
        )
        self._persist_success(report, raw_delta_link=effective_delta, res=res, dry_run=dry_run)
        return report

    # -- persistence (raw delta_link → SQLite only) -------------------------

    def _finish_rebaseline(
        self, base: dict[str, Any], logical_endpoint: str, started_from: str, dry_run: bool
    ) -> DeltaSyncReport:
        report = DeltaSyncReport(
            status="requires_rebaseline",
            endpoint=logical_endpoint,
            started_from=started_from,
            error_redacted="graph_410_stale_delta_token",
            note="stale delta token; cleared — next run re-baselines",
            **base,
        )
        if not dry_run and self._store is not None:
            now = _utc_now()
            # Clear the stale token; record the explicit status (no silent discard).
            self._store.upsert_source_sync_state(
                source_id=report.source_id,
                delta_link=None,
                delta_link_fingerprint=None,
                last_attempted_sync_utc=now,
                sync_status="requires_rebaseline",
                error_message_redacted="graph_410_stale_delta_token",
            )
            self._store.insert_processing_receipt(
                receipt_id=str(uuid.uuid4()),
                source_id=report.source_id,
                operation="delta_sync",
                status=report.status,
                detail=report.model_dump(),
            )
        return report

    def _persist_success(
        self, report: DeltaSyncReport, *, raw_delta_link: Optional[str], res: Any, dry_run: bool
    ) -> None:
        if dry_run or self._store is None:
            return
        now = _utc_now()
        self._store.upsert_source_sync_state(
            source_id=report.source_id,
            drive_id=res.drive_id,
            folder_item_id=res.folder_item_id,
            delta_link=raw_delta_link,  # raw token: SQLite ONLY
            delta_link_fingerprint=delta_link_fingerprint(raw_delta_link),
            last_successful_sync_utc=now if report.status == "ok" else None,
            last_attempted_sync_utc=now,
            last_change_count=report.items_seen,
            sync_status=report.status,
        )
        self._record_run_and_receipt(report, res)

    def _persist_attempt(
        self, report: DeltaSyncReport, *, delta_link: Optional[str], dry_run: bool, res: Any
    ) -> None:
        if dry_run or self._store is None:
            return
        now = _utc_now()
        self._store.upsert_source_sync_state(
            source_id=report.source_id,
            drive_id=res.drive_id,
            folder_item_id=res.folder_item_id,
            last_attempted_sync_utc=now,
            sync_status="error",
            error_message_redacted=report.error_redacted,
        )
        self._record_run_and_receipt(report, res)

    def _record_run_and_receipt(self, report: DeltaSyncReport, res: Any) -> None:
        if self._store is None:
            return
        now = _utc_now()
        self._store.insert_source_crawl_run(
            run_id=report.run_id,
            source_id=report.source_id,
            source_scope=report.scope or report.kind,
            mode="apply",
            started_at=now,
            completed_at=now,
            pages_seen=report.pages_seen,
            items_seen=report.items_seen,
            items_in_scope=report.items_changed,
            items_out_of_scope_filtered=report.items_deleted,
            delta_link_recorded=report.delta_link_recorded,
            status=report.status,
            error_redacted=report.error_redacted,
        )
        self._store.insert_processing_receipt(
            receipt_id=str(uuid.uuid4()),
            source_id=report.source_id,
            operation="delta_sync",
            status=report.status,
            detail=report.model_dump(),
        )
