"""Phase 10 — source-ref gate for the model-facing daily-brief context (usefulness repair).

Enforces the contract that the local model only ever sees *source-linked* deterministic candidates.
The audit found `candidate_source_ref_coverage = 0.0` while the model still emitted source-looking
bullets; with Priority 3 persisting `candidate_source_refs`, this gate (Priority 4) drops any
candidate lacking a source ref from the model context, reports coverage + omissions, and signals when
synthesis must be withheld (candidates exist but none are source-linked).

Read-only: no writeback, no model call. Operates on already-redacted candidate rows + hashed refs.
"""

from __future__ import annotations

from typing import Any, Optional

from .daily_brief_candidate_writer import CANDIDATE_TYPE

# Executive / top-priority sections: a `success` brief requires 100% source-ref coverage here.
EXECUTIVE_SECTIONS: frozenset[str] = frozenset({"actions", "procore", "calendar", "follow_up", "waiting"})

_SHORT_ID = 18


def _short(value: Any) -> str:
    return str(value or "")[:_SHORT_ID]


def gate_model_candidate_context(
    store: Any,
    brief_date: str,
    *,
    max_per_section: int = 12,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Build the gated, source-linked candidate context for the model + a coverage report.

    Returns ``(candidates_by_section, report)`` where ``candidates_by_section`` contains ONLY
    candidates with >=1 ``daily_brief_action`` source ref (capped per section), and ``report`` carries
    total/linked counts, overall + executive coverage, withheld ids, the set of model-supported short
    ids, ``withhold_synthesis`` (candidates exist but none are linked), and a verdict.
    """
    rows = store.list_daily_brief_action_candidates(brief_date=brief_date, limit=100000)

    by_section: dict[str, list[dict[str, Any]]] = {}
    supported_short_ids: set[str] = set()
    withheld_ids: list[str] = []
    exec_total = 0
    exec_linked = 0
    linked = 0

    for r in rows:
        cid = str(r.get("daily_brief_action_candidate_id"))
        section = str(r.get("section") or "__unassigned__")
        is_exec = section in EXECUTIVE_SECTIONS
        if is_exec:
            exec_total += 1
        refs = store.list_candidate_source_refs(candidate_type=CANDIDATE_TYPE, candidate_id=cid)
        if not refs:
            withheld_ids.append(cid)
            continue
        linked += 1
        if is_exec:
            exec_linked += 1
        supported_short_ids.add(_short(cid))
        bucket = by_section.setdefault(section, [])
        if len(bucket) >= max_per_section:
            continue
        bucket.append(
            {
                "id": _short(cid),
                "title": r.get("title_redacted"),
                "project": r.get("project_key") or "Needs Project Review",
                "priority": r.get("priority"),
                "reason": r.get("reason_redacted"),
                "next_action": r.get("recommended_next_action"),
                "source_ref_count": len(refs),
            }
        )

    total = len(rows)
    report = {
        "total_candidates": total,
        "source_linked_candidates": linked,
        "coverage": round(linked / total, 4) if total else 1.0,
        "executive_total": exec_total,
        "executive_source_linked": exec_linked,
        "executive_coverage": round(exec_linked / exec_total, 4) if exec_total else 1.0,
        "withheld_candidate_count": len(withheld_ids),
        "withheld_candidate_ids": withheld_ids,
        "supported_short_ids": sorted(supported_short_ids),
        "withhold_synthesis": total > 0 and linked == 0,
        "verdict": (
            "no_candidates"
            if total == 0
            else ("degraded_no_source_linked_context" if linked == 0 else "ok")
        ),
    }
    return by_section, report


def drop_unsupported_bullets(
    bullets: list[dict[str, Any]],
    supported_short_ids: set[str],
    *,
    id_key: str = "source_id",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split model bullets into (supported, dropped).

    A bullet that cites a ``source_id`` is supported only if that id is in the source-linked set; a
    bullet with no id is treated as unsupported (the model must cite a source-linked candidate to
    claim a meeting / Procore risk / follow-up / action). Returns ``(kept, dropped)``.
    """
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for b in bullets:
        sid = _short(b.get(id_key))
        if sid and sid in supported_short_ids:
            kept.append(b)
        else:
            dropped.append(b)
    return kept, dropped


def executive_coverage_ok(report: Optional[dict[str, Any]]) -> bool:
    """True when executive/top-priority rows are 100% source-linked (required for `success`)."""
    if not report:
        return True
    return float(report.get("executive_coverage", 1.0)) >= 1.0
