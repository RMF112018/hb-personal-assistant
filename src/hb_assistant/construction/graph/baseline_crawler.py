"""Phase 06A — bounded, metadata-only baseline crawl for approved sources.

The baseline crawl is the first full enumeration of a source's drive items before
delta hardening (Prompt 08). It prefers delta initial enumeration (full
representation, no token stored here), supports a bounded non-recursive children
traversal for *targeted diagnostics only*, and records a crawl-run accounting row
(`construction_source_crawl_runs`) + a processing receipt with counts and redacted
errors.

Bounds: ``max_pages``, ``max_items``, and a ``max_seconds`` wall-clock budget, plus
the read-endpoint allowlist guard. Metadata only — no document content is read,
``@microsoft.graph.downloadUrl`` is never touched, and no delta token is persisted
(baseline records ``delta_link_recorded = False``). Reuses the Prompt 06
``normalize_drive_item`` + ``upsert_drive_item`` for the rich V5 shape on apply.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.drive_item_indexer import (
    normalize_drive_item,
    redacted_sample,
)
from hb_assistant.construction.graph.resolver import ConstructionGraphResolver
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.files_endpoint_guard import assert_files_request_allowed
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

GRAPH_SCOPES = ["Files.ReadWrite.All", "User.Read"]
_DEFAULT_MAX_PAGES = 5
_DEFAULT_MAX_ITEMS = 500
_DEFAULT_MAX_SECONDS = 300
_SAMPLE_LIMIT = 10
_ME_DRIVE_KINDS = {"onedrive_business_root", "onedrive_personal_root", "onedrive_personal"}


class CrawlRunReport(BaseModel):
    run_id: str
    source_id: str
    kind: str
    scope: Optional[str] = None
    mode: str  # dry_run | apply
    traversal: str  # delta | children
    endpoint: Optional[str] = None
    status: str  # ok | partial | pending | unsupported | error
    pages_seen: int = 0
    items_seen: int = 0
    items_in_scope: int = 0
    items_out_of_scope_filtered: int = 0
    items_persisted: int = 0
    max_pages: int = _DEFAULT_MAX_PAGES
    max_items: int = _DEFAULT_MAX_ITEMS
    max_seconds: int = _DEFAULT_MAX_SECONDS
    truncated_by: str = "none"  # none | max_pages | max_items | max_seconds
    delta_link_recorded: bool = False
    sample: list[dict[str, Any]] = Field(default_factory=list)
    note: Optional[str] = None
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class BaselineCrawler:
    """Bounded, metadata-only baseline enumeration → crawl-run accounting + V5 rows."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        store: Optional[ConstructionStore] = None,
    ) -> None:
        self._http = http_client
        self._store = store
        self._resolver = ConstructionGraphResolver(http_client)

    def _select_endpoint(self, res: Any, *, children: bool) -> Optional[str]:
        if children:
            if res.drive_id and res.folder_item_id:
                return f"/drives/{res.drive_id}/items/{res.folder_item_id}/children"
            if res.drive_id:
                return f"/drives/{res.drive_id}/root/children"
            return None  # children diagnostics need a resolved drive
        if res.drive_id and res.folder_item_id:
            return f"/drives/{res.drive_id}/items/{res.folder_item_id}/delta"
        if res.drive_id:
            return f"/drives/{res.drive_id}/root/delta"
        if res.kind in _ME_DRIVE_KINDS:
            return "/me/drive/root/delta"
        return None

    def crawl(
        self,
        source: SourceLocation,
        *,
        dry_run: bool = True,
        max_pages: int = _DEFAULT_MAX_PAGES,
        max_items: int = _DEFAULT_MAX_ITEMS,
        max_seconds: int = _DEFAULT_MAX_SECONDS,
        children: bool = False,
    ) -> CrawlRunReport:
        run_id = str(uuid.uuid4())
        traversal = "children" if children else "delta"
        res = self._resolver.resolve(source)
        scope = res.scope or source.kind
        base: dict[str, Any] = {
            "run_id": run_id,
            "source_id": source.source_key,
            "kind": source.kind,
            "scope": scope,
            "mode": "dry_run" if dry_run else "apply",
            "traversal": traversal,
            "max_pages": max_pages,
            "max_items": max_items,
            "max_seconds": max_seconds,
        }
        if res.status == "unsupported":
            return CrawlRunReport(status="unsupported", **base)
        endpoint = self._select_endpoint(res, children=children)
        if endpoint is None:
            return CrawlRunReport(
                status="pending",
                note=res.error_redacted or "drive_id unresolved; cannot crawl",
                **base,
            )

        started = time.monotonic()
        pages_seen = items_seen = in_scope = out_of_scope = persisted = 0
        sample: list[dict[str, Any]] = []
        truncated_by = "none"
        path: Optional[str] = endpoint
        params: Optional[dict[str, Any]] = {"$top": str(min(max_items, 200))}
        done = False
        try:
            while path is not None and not done:
                if (time.monotonic() - started) >= max_seconds:
                    truncated_by = "max_seconds"
                    break
                if pages_seen >= max_pages:
                    truncated_by = "max_pages"
                    break
                assert_files_request_allowed("GET", path)  # allowlist guard, GET-only
                data = self._http.get(path, params=params, scopes=GRAPH_SCOPES)
                pages_seen += 1
                for item in data.get("value", []) or []:
                    if items_seen >= max_items:
                        truncated_by = "max_items"
                        done = True
                        break
                    items_seen += 1
                    kwargs = normalize_drive_item(
                        source.source_key,
                        res.drive_id or "",
                        item,
                        project_key=source.project_key,
                    )
                    if not kwargs.get("drive_item_id"):
                        out_of_scope += 1
                        continue
                    if kwargs.get("deleted"):
                        out_of_scope += 1
                    else:
                        in_scope += 1
                        if not dry_run and self._store is not None:
                            self._store.upsert_drive_item(**kwargs)
                            persisted += 1
                    if len(sample) < _SAMPLE_LIMIT:
                        sample.append(redacted_sample(kwargs))
                if done:
                    break
                next_link = data.get("@odata.nextLink")
                if not next_link:
                    break
                path = next_link  # absolute continuation; query is stripped by the guard
                params = None
        except GraphHttpError as e:
            report = CrawlRunReport(
                status="error",
                endpoint=endpoint,
                pages_seen=pages_seen,
                items_seen=items_seen,
                items_in_scope=in_scope,
                items_out_of_scope_filtered=out_of_scope,
                error_redacted=f"graph_{e.status}",
                **base,
            )
            self._persist(report, started, dry_run)
            return report

        report = CrawlRunReport(
            status="partial" if truncated_by != "none" else "ok",
            endpoint=endpoint,
            pages_seen=pages_seen,
            items_seen=items_seen,
            items_in_scope=in_scope,
            items_out_of_scope_filtered=out_of_scope,
            items_persisted=persisted,
            truncated_by=truncated_by,
            sample=sample,
            **base,
        )
        self._persist(report, started, dry_run)
        return report

    def _persist(self, report: CrawlRunReport, started: float, dry_run: bool) -> None:
        if dry_run or self._store is None:
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
            items_in_scope=report.items_in_scope,
            items_out_of_scope_filtered=report.items_out_of_scope_filtered,
            delta_link_recorded=False,
            status=report.status,
            error_redacted=report.error_redacted,
        )
        self._store.insert_processing_receipt(
            receipt_id=str(uuid.uuid4()),
            source_id=report.source_id,
            operation="baseline_crawl",
            status=report.status,
            detail=report.model_dump(),
        )


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
