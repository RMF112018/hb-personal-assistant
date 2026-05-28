"""WorkstreamContext: assembles redacted, source-linked context for a work period (e.g. today) from retrieval + store signals.

Used by briefs, action refresh, meeting prep etc. (future consumers).
Phase 11: thin assembler using Retriever + direct store queries for actions/mentions.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field

from hb_assistant.store.repositories import Store

from .retriever import Retriever


@dataclass
class WorkstreamContext:
    """Redacted context bundle for a target date / focus."""

    target_date: str
    query_hints: list[str] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)  # hits from retriever (excerpts + links)
    recent_actions: list[dict] = field(default_factory=list)
    mentions: list[dict] = field(default_factory=list)
    files_indexed: int = 0
    notes: str = "redacted; source-linked; deterministic + semantic (if enabled)"


class WorkstreamContextBuilder:
    """Builds WorkstreamContext. Dry run / mock friendly. No full content."""

    def __init__(self, store: Store | None = None, retriever: Retriever | None = None):
        self.store = store or Store()
        self.retriever = retriever or Retriever(store=self.store)

    def build_for_today(
        self,
        *,
        focus_queries: list[str] | None = None,
        limit_per: int = 5,
        include_actions: bool = True,
    ) -> WorkstreamContext:
        focus = focus_queries or ["action items", "decisions", "waiting on", "key files"]
        retrieved = []
        for q in focus[:3]:
            hits = self.retriever.search(q, limit=limit_per)
            for h in hits:
                retrieved.append({
                    "query": q,
                    "source_record_id": h.source_record_id,
                    "type": h.content_type,
                    "excerpt": h.text_excerpt[:500],
                    "score": h.score,
                    "links": h.links or [],
                })

        actions = []
        if include_actions:
            with suppress(Exception):
                actions = self.store.get_recent_action_items(limit=10) or []

        mentions = self.store.list_recent_body_mentions(limit=limit_per) or []

        return WorkstreamContext(
            target_date="today",
            query_hints=focus,
            retrieved=retrieved,
            recent_actions=actions,
            mentions=mentions,
            files_indexed=len([r for r in retrieved if "file" in str(r.get("type"))]),
        )
