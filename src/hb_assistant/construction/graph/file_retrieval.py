"""Phase 06A — source-linked retrieval over SharePoint / OneDrive bounded excerpts.

Deterministic, **offline** keyword retrieval over the bounded redacted parser
excerpts in V19 ``construction_file_extraction_runs`` (Prompt 11). Each hit is
linked back to its source for full traceability — drive item identity + web URL,
project identity, the parser output id (the extraction run), and the processing
receipt id (the controlled-download receipt). Bounded excerpts only; full
document text is never stored or returned.

Scoring reuses the deterministic pattern from ``retrieval/retriever.py``
(query-term overlap + exact-phrase boost, capped at 1.0) but runs against the
construction store — no embeddings, no Ollama, no Graph — so the proof is fully
reproducible. Review-routed / sensitive files are excluded (a run flagged
``review_required`` or a drive item sitting in the open review queue is never
surfaced), so sensitive-file routing is never bypassed.

Read-only against Microsoft 365 and SQLite; no writeback; broad Graph file
permission tightening remains deferred.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.graph.controlled_extraction import _bounded_redact
from hb_assistant.construction.store import ConstructionStore


class FileRetrievalHit(BaseModel):
    source_id: str
    project_key: Optional[str] = None
    drive_id: Optional[str] = None
    drive_item_id: str
    name_redacted: Optional[str] = None
    web_url: Optional[str] = None
    parent_path: Optional[str] = None
    excerpt_redacted: str
    score: float
    parser_output_id: str  # = extraction_id
    parser_name: Optional[str] = None
    processing_receipt_id: Optional[str] = None
    content_hash: Optional[str] = None
    char_count: int = 0
    created_utc: Optional[str] = None

    model_config = {"extra": "forbid"}


class FileRetrievalReport(BaseModel):
    query: str
    project_key: Optional[str] = None
    source_id: Optional[str] = None
    limit: int
    ok: bool = True
    hit_count: int = 0
    candidates_considered: int = 0
    review_routed_excluded: int = 0
    hits: list[FileRetrievalHit] = Field(default_factory=list)
    guardrails: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class FileRetriever:
    """Offline, deterministic source-linked retrieval over bounded file excerpts."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store

    def retrieve(
        self,
        *,
        query: str,
        project_key: Optional[str] = None,
        source_id: Optional[str] = None,
        limit: int = 10,
    ) -> FileRetrievalReport:
        runs = self._store.list_file_extraction_runs(source_id=source_id, limit=100000)
        q_terms = {t.lower() for t in query.split() if len(t) > 2}
        phrase = query.strip().lower()

        # Per-source review-queue exclusion set (sensitive routing must not be bypassed).
        review_queued: dict[str, set[str]] = {}
        receipts_by_source: dict[str, dict[str, str]] = {}

        considered = 0
        excluded = 0
        scored: list[tuple[float, FileRetrievalHit]] = []
        for run in runs:
            if project_key is not None and run.get("project_key") != project_key:
                continue
            considered += 1
            sid = run["source_id"]
            iid = run["drive_item_id"]
            if run.get("review_required") or iid in self._review_queue_items(sid, review_queued):
                excluded += 1
                continue

            excerpt = _bounded_redact(run.get("text_excerpt_redacted") or "")
            item = self._store.get_drive_item(source_id=sid, drive_item_id=iid) or {}
            name = item.get("name") or ""
            score = self._score(q_terms=q_terms, phrase=phrase, text=f"{excerpt} {name}".lower())
            if score <= 0.0:
                continue

            scored.append(
                (
                    score,
                    FileRetrievalHit(
                        source_id=sid,
                        project_key=run.get("project_key"),
                        drive_id=run.get("drive_id") or item.get("drive_id"),
                        drive_item_id=iid,
                        name_redacted=_bounded_redact(name, max_chars=200) or None,
                        web_url=item.get("web_url"),
                        parent_path=item.get("parent_reference_path") or item.get("path"),
                        excerpt_redacted=excerpt,
                        score=round(score, 4),
                        parser_output_id=run["extraction_id"],
                        parser_name=run.get("parser_name"),
                        processing_receipt_id=self._receipt_id(sid, iid, receipts_by_source),
                        content_hash=run.get("content_hash"),
                        char_count=int(run.get("char_count") or len(excerpt)),
                        created_utc=run.get("created_utc"),
                    ),
                )
            )

        scored.sort(key=lambda pair: pair[0], reverse=True)
        hits = [hit for _score, hit in scored[:limit]]
        return FileRetrievalReport(
            query=query,
            project_key=project_key,
            source_id=source_id,
            limit=limit,
            ok=True,
            hit_count=len(hits),
            candidates_considered=considered,
            review_routed_excluded=excluded,
            hits=hits,
            guardrails={
                "external_systems": "read_only",
                "writeback": "none",
                "graph_calls": "none",
                "full_text_persisted": False,
                "excerpt_bounded_redacted": True,
                "source_linked": True,
                "review_routed_excluded": True,
                "permission_tightening": "deferred",
            },
        )

    @staticmethod
    def _score(*, q_terms: set[str], phrase: str, text: str) -> float:
        if not q_terms:
            return 0.0
        overlap = sum(1 for t in q_terms if t in text)
        score = overlap / len(q_terms)
        if phrase and phrase in text:
            score += 0.3
        return min(1.0, score)

    def _review_queue_items(self, source_id: str, cache: dict[str, set[str]]) -> set[str]:
        if source_id not in cache:
            cache[source_id] = {
                row["item_id"]
                for row in self._store.list_review_queue(
                    source_key=source_id, status="open", limit=100000
                )
            }
        return cache[source_id]

    def _receipt_id(
        self, source_id: str, drive_item_id: str, cache: dict[str, dict[str, str]]
    ) -> Optional[str]:
        if source_id not in cache:
            mapping: dict[str, str] = {}
            # Receipts are ordered newest-first; keep the first (latest) per item.
            for r in self._store.list_download_receipts(source_id=source_id, limit=100000):
                mapping.setdefault(r["drive_item_id"], r["receipt_id"])
            cache[source_id] = mapping
        return cache[source_id].get(drive_item_id)
