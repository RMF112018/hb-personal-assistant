"""Retriever: deterministic + gated semantic retrieval over store content (excerpts, titles, etc).

Phase 11: loads redacted bounded content from parser_outputs, emails, etc via Store.
Combines keyword (deterministic) + optional semantic (embed + cosine) ranking.
All results carry source links for provenance. Redacted outputs only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hb_assistant.store.repositories import Store

from .embedder import Embedder, OllamaEmbedder


@dataclass
class RetrievalHit:
    source_record_id: int
    content_type: str  # "parser_excerpt", "email_preview", etc
    text_excerpt: str  # bounded redacted
    score: float
    links: list[dict] = None  # source_links
    metadata: dict[str, Any] = None  # name, date hints etc (redacted)


def retrieve_email_calendar_structured(
    construction_store: Any,
    *,
    query: str = "",
    project_key: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Private raw-aware retrieval read model over the V49 structured projection layer.

    Ranks email message + calendar event structured projection rows by deterministic keyword
    overlap (matched against local-private subjects in the private DB) but returns **redacted**
    results only: a hashed subject ref, the selected source-tier + source-quality, and content
    availability flags — never raw subjects, bodies, or join URLs. Prefers higher source-quality
    rows so a lower-quality projection can never outrank a structured-full one.
    """
    from hb_assistant.construction.email_calendar.source_quality import rank as _rank
    from hb_assistant.normalize.redaction import hash_value

    terms = [t for t in (query or "").lower().split() if t]

    def _score(subject: str | None, sq: str | None) -> float:
        subj = (subject or "").lower()
        kw = sum(1 for t in terms if t in subj) if terms else 0
        return kw * 10.0 + _rank(sq) / 100.0

    rows: list[dict[str, Any]] = []
    for r in construction_store.list_email_message_structured(project_key=project_key, limit=500):
        rows.append(
            {
                "content_type": "email_message_structured",
                "subject_ref": hash_value(r.get("subject") or ""),
                "selected_source": "structured",
                "source_quality": r.get("source_quality"),
                "has_body_text": bool(r.get("body_text_available")),
                "project_key": r.get("project_key"),
                "received_at_utc": r.get("received_at_utc"),
                "_score": _score(r.get("subject"), r.get("source_quality")),
            }
        )
    for r in construction_store.list_event_structured(project_key=project_key, limit=500):
        rows.append(
            {
                "content_type": "calendar_event_structured",
                "subject_ref": hash_value(r.get("subject") or ""),
                "selected_source": "structured",
                "source_quality": r.get("source_quality"),
                "has_body_text": bool(r.get("body_text_available")),
                "has_join_url": bool(r.get("has_join_url")),
                "project_key": r.get("project_key"),
                "start_datetime_utc": r.get("start_datetime_utc"),
                "_score": _score(r.get("subject"), r.get("source_quality")),
            }
        )
    rows.sort(key=lambda x: x["_score"], reverse=True)
    for x in rows:
        x["score"] = round(x.pop("_score"), 4)
    return rows[: max(0, limit)]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb + 1e-9)


class Retriever:
    """Main retrieval orchestrator. Dry-run / mock friendly."""

    def __init__(
        self,
        store: Store | None = None,
        embedder: Embedder | None = None,
        *,
        semantic_enabled: bool = True,
        max_candidates: int = 200,
    ):
        self.store = store or Store()
        self.embedder = embedder or OllamaEmbedder()
        self.semantic_enabled = semantic_enabled
        self.max_candidates = max_candidates

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        content_types: list[str] | None = None,
        use_semantic: bool | None = None,
    ) -> list[RetrievalHit]:
        """Return ranked hits. Always redacted excerpts + links. Never full content."""
        if not query or not query.strip():
            return []
        use_sem = self.semantic_enabled if use_semantic is None else use_semantic
        q = query.strip()[:200]

        # 1. Load candidates (bounded recent from known tables with text)
        candidates: list[dict[str, Any]] = []
        # parser_outputs excerpts (from files)
        try:
            # use existing helper if present, else raw via store conn? For now use get_files_by_status + list_parser
            # simplified: query recent parser_outputs via new helper or direct (we'll ensure store has)
            pos = (
                self.store.list_recent_parser_outputs(limit=self.max_candidates)
                if hasattr(self.store, "list_recent_parser_outputs")
                else []
            )
            for p in pos:
                candidates.append(
                    {
                        "source_record_id": p.get("file_source_record_id"),
                        "content_type": "parser_excerpt",
                        "text": p.get("text_excerpt", "") or "",
                        "meta": {"parser": p.get("parser_name")},
                    }
                )
        except Exception:
            pass

        # Note: email previews not persisted as full text in schema (phase 6 flags only); focus on parser_outputs excerpts for file/work product retrieval (main Phase 10+ source)

        if not candidates:
            return []

        # 2. Deterministic keyword filter / score (simple overlap)
        q_terms = {t.lower() for t in q.split() if len(t) > 2}
        scored: list[tuple[float, dict]] = []
        for c in candidates:
            txt = (c.get("text") or "").lower()
            if not txt:
                continue
            overlap = sum(1 for t in q_terms if t in txt)
            base = overlap / max(1, len(q_terms)) if q_terms else 0.0
            # boost exact phrase
            if q.lower() in txt:
                base += 0.3
            scored.append((min(1.0, base), c))

        # sort det first
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: max(limit * 3, 30)]

        # 3. Optional semantic rerank / blend
        if use_sem and top:
            try:
                qvec = self.embedder.embed(q)
                sem_scored = []
                for det_score, c in top:
                    tvec = self.embedder.embed(c.get("text", "")[:2000])
                    sem = _cosine(qvec, tvec)
                    # blend det + sem
                    final = 0.4 * det_score + 0.6 * max(0.0, sem)
                    sem_scored.append((final, c, sem))
                sem_scored.sort(key=lambda x: x[0], reverse=True)
                top = [(s, c) for s, c, _ in sem_scored]
            except Exception:
                pass  # keep det only on error

        hits: list[RetrievalHit] = []
        for score, c in top[:limit]:
            sid = c.get("source_record_id")
            links = []
            try:
                if sid:
                    links = self.store.get_links_for_source(sid) or []
            except Exception:
                pass
            hits.append(
                RetrievalHit(
                    source_record_id=sid or 0,
                    content_type=c.get("content_type", "unknown"),
                    text_excerpt=(c.get("text") or "")[:2000],  # extra bound for output
                    score=round(score, 4),
                    links=links,
                    metadata=c.get("meta"),
                )
            )
        return hits
