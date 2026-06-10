"""Phase 10 — central daily-brief candidate persistence contract (daily-brief usefulness repair).

The single place that persists a deterministic daily-brief action candidate **and** its source-ref
links. Every projection stage (calendar prep, Procore digest, …) routes its writes through
:func:`persist_candidate_with_refs` so candidate-id derivation, source-ref hashing, and idempotency
live in exactly one place — stages never hand-roll those concerns. This closes the audit gap where
candidates were written but ``candidate_source_refs`` stayed empty (coverage 0.0): the model-facing
gate (Priority 4) can now require source-linked rows.

Safety: source refs are stored hash-only (``sha256`` of the already-redacted/deterministic ref);
guard columns are omitted on insert → DEFAULT 0 / CHECK(=0). No raw bodies/URLs/tokens. Idempotent:
the candidate id is derived from (brief_date, section, group_key) and each ref id from
(candidate_id, family, ref), so repeat runs are no-ops.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional

CANDIDATE_TYPE = "daily_brief_action"


@dataclass(frozen=True)
class CandidateWriteReceipt:
    row_id: str
    inserted: bool
    refs_written: int


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def candidate_row_id(store: Any, *, brief_date: str, section: str, group_key: str) -> str:
    """Canonical candidate id (delegates to the store's shared derivation — never re-implemented)."""
    return store.daily_brief_action_candidate_id_for(brief_date, section, group_key)


def persist_candidate_with_refs(
    store: Any,
    *,
    brief_date: str,
    section: str,
    title_redacted: str,
    confidence: float,
    group_key: str,
    source_refs: list[dict[str, Any]],
    project_key: Optional[str] = None,
    priority: int = 100,
    reason_redacted: Optional[str] = None,
    recommended_next_action: Optional[str] = None,
) -> CandidateWriteReceipt:
    """Persist one daily-brief action candidate and its hashed source refs (idempotent).

    Returns a receipt with the derived ``row_id``, whether a NEW candidate row was inserted, and how
    many source refs were upserted. Source refs are upserted even when the candidate already existed
    (idempotent), so coverage is repaired for rows persisted by an earlier partial run.
    """
    row_id = candidate_row_id(store, brief_date=brief_date, section=section, group_key=group_key)
    inserted = store.insert_daily_brief_action_candidate(
        brief_date=brief_date,
        section=section,
        title_redacted=title_redacted,
        confidence=confidence,
        project_key=project_key,
        priority=priority,
        reason_redacted=reason_redacted,
        recommended_next_action=recommended_next_action,
        group_key=group_key,
    )
    refs_written = 0
    for ref in source_refs or []:
        family = str(ref.get("source_family") or "").strip()
        raw_ref = str(ref.get("source_ref") or "").strip()
        if not family or not raw_ref:
            continue
        store.upsert_candidate_source_ref(
            source_ref_id=f"dbsr-{_hash(f'{row_id}|{family}|{raw_ref}')[:32]}",
            candidate_type=CANDIDATE_TYPE,
            candidate_id=row_id,
            source_family=family,
            source_ref_hash=_hash(raw_ref),
            source_table=ref.get("source_table"),
        )
        refs_written += 1
    return CandidateWriteReceipt(row_id=row_id, inserted=inserted, refs_written=refs_written)


def candidate_source_ref_coverage(
    store: Any, *, brief_date: str, section: Optional[str] = None
) -> dict[str, Any]:
    """Compute source-ref coverage for persisted candidates on ``brief_date`` (optionally a section).

    Returns total candidates, how many have >=1 ``daily_brief_action`` source ref, the coverage ratio
    (1.0 when there are no candidates), and the ids of any uncovered rows. Pure read; no writes.
    """
    candidates = store.list_daily_brief_action_candidates(brief_date=brief_date, section=section)
    total = len(candidates)
    covered = 0
    uncovered: list[str] = []
    for c in candidates:
        cid = str(c.get("daily_brief_action_candidate_id"))
        refs = store.list_candidate_source_refs(candidate_type=CANDIDATE_TYPE, candidate_id=cid)
        if refs:
            covered += 1
        else:
            uncovered.append(cid)
    coverage = (covered / total) if total else 1.0
    return {
        "brief_date": brief_date,
        "section": section,
        "total_candidates": total,
        "covered_candidates": covered,
        "coverage": round(coverage, 4),
        "uncovered_candidate_ids": uncovered,
    }
