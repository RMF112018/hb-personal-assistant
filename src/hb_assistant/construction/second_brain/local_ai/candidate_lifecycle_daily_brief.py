"""Phase 10 V50 — lifecycle-aware daily-brief view + stage context.

Turns the unified review queue into the sections the daily brief distinguishes (new review,
accepted, waiting-on-others, commitments, stale, snoozed-returning, project-review-required,
source-missing-withheld) without misleading success: rejected/suppressed/merged/closed and
future-snoozed rows are hidden from the normal view but still counted, and source-missing
actionable rows are withheld with an explicit degraded status rather than silently dropped.

Also exposes :func:`lifecycle_stage_context` for the usefulness gate so lifecycle contradictions
cannot report success. Raw-safe: only bounded redacted titles, counts, states, and codes are
emitted — never raw bodies/HTML/URLs/recipients/tokens/prompts.
"""

from __future__ import annotations

from typing import Any, Optional

from . import candidate_lifecycle as lc
from .candidate_lifecycle_read_model import build_review_queue


def _snoozed_returning(store: Any, now_utc: str) -> list[dict[str, Any]]:
    """Subjects whose latest overlay event is a snooze that has now reached its return date."""
    returning: list[dict[str, Any]] = []
    for (stype, sid), ev in store.latest_lifecycle_states().items():
        if ev.get("event_type") == lc.EVENT_SNOOZE:
            until = ev.get("effective_until_utc")
            if until and not lc.is_future(until, now_utc):
                returning.append({"subject_type": stype, "subject_id": sid,
                                  "returned_on_utc": until})
    returning.sort(key=lambda r: (r["subject_type"], r["subject_id"]))
    return returning


def build_daily_brief_lifecycle_view(
    store: Any, *, now_utc: Optional[str] = None
) -> dict[str, Any]:
    """Build the lifecycle-aware daily-brief view. Default (hidden-excluded) sections + counts."""
    now = now_utc or lc.utc_now()
    full = build_review_queue(store, now_utc=now, include_hidden=True)
    rows = full["rows"]

    sections: dict[str, list[dict[str, Any]]] = {
        "new_review": [],
        "accepted_actions": [],
        "user_commitments": [],
        "waiting_on_others": [],
        "stale_actions": [],
        "project_review_required": [],
        "source_missing_withheld": [],
    }
    hidden_counts = {"rejected": 0, "suppressed": 0, "merged": 0, "closed": 0, "snoozed_future": 0}

    for r in rows:
        # A promoted task/commitment candidate is represented by its accepted_* row — skip the
        # duplicate candidate entry so the brief does not double-count it.
        if r.get("promoted") and r["subject_type"] in ("task_candidate", "commitment_candidate"):
            continue
        state = r["lifecycle_state"]
        if state == lc.STATE_REJECTED:
            hidden_counts["rejected"] += 1
            continue
        if state == lc.STATE_SUPPRESSED:
            hidden_counts["suppressed"] += 1
            continue
        if state == lc.STATE_MERGED:
            hidden_counts["merged"] += 1
            continue
        if state == lc.STATE_CLOSED:
            hidden_counts["closed"] += 1
            continue
        if state == lc.STATE_SNOOZED:
            hidden_counts["snoozed_future"] += 1
            continue
        # visible states
        if state == lc.STATE_SOURCE_MISSING:
            sections["source_missing_withheld"].append(r)
        elif state == lc.STATE_PROJECT_REVIEW_REQUIRED:
            sections["project_review_required"].append(r)
        elif state == lc.STATE_STALE:
            sections["stale_actions"].append(r)
        elif state == lc.STATE_ACCEPTED:
            if r["family"] in ("commitment", "accepted_commitment"):
                sections["user_commitments"].append(r)
            elif r["family"] == "waiting" or r["subject_type"] == "follow_up_watch":
                sections["waiting_on_others"].append(r)
            else:
                sections["accepted_actions"].append(r)
        else:  # new / needs_review
            sections["new_review"].append(r)

    returning = _snoozed_returning(store, now)
    section_counts = {k: len(v) for k, v in sections.items()}
    has_useful = any(
        section_counts[k] for k in ("new_review", "accepted_actions", "user_commitments",
                                    "waiting_on_others", "stale_actions", "project_review_required")
    )
    return {
        "generated_utc": now,
        "sections": sections,
        "section_counts": section_counts,
        "hidden_counts": hidden_counts,
        "snoozed_returning": returning,
        "snoozed_returning_count": len(returning),
        "has_useful_content": has_useful,
        "guardrails": {"raw_safe": True, "deterministic": True, "local_only": True},
    }


def lifecycle_stage_context(store: Any, *, now_utc: Optional[str] = None) -> dict[str, Any]:
    """Lifecycle metrics + contradiction flags for the usefulness gate (see usefulness_scorecard)."""
    now = now_utc or lc.utc_now()
    full = build_review_queue(store, now_utc=now, include_hidden=True)
    rows = full["rows"]
    state_counts = full["state_counts"]
    total_candidates = len(rows)

    # Accepted actions that lack source-ref traceability (should be impossible post-gate). Accepted
    # task/commitment rows must trace to refs via their candidate id (source_ref_propagation_contract).
    accepted_missing_source = sum(
        1
        for r in rows
        if r["lifecycle_state"] == lc.STATE_ACCEPTED
        and r["subject_type"] in ("accepted_task", "accepted_commitment")
        and r["source_ref_count"] == 0
    )
    # Source-ref coverage for SURFACED, source-required rows (the default review queue). A
    # source_missing row is surfaced (withheld/degraded) and counts as uncovered, so coverage
    # below 1.0 honestly flags that an uncovered row reached the operator's view.
    visible_default_rows = build_review_queue(store, now_utc=now, include_hidden=False)["rows"]
    surfaced = [r for r in visible_default_rows if r["subject_type"] in lc.SOURCE_REQUIRED_SUBJECTS]
    actionable_total = len(surfaced)
    actionable_covered = sum(1 for r in surfaced if r["source_ref_coverage_status"] == "ok")
    coverage = (actionable_covered / actionable_total) if actionable_total else 1.0

    # Duplicate inflation: two DISTINCT same-family visible subjects sharing a duplicate group key
    # (a candidate and its own promoted accepted row are the same item, so group by subject_type
    # and skip promoted candidate rows).
    visible_groups: dict[tuple[str, str], int] = {}
    for r in rows:
        if r["hidden_from_daily_brief"]:
            continue
        if r.get("promoted") and r["subject_type"] in ("task_candidate", "commitment_candidate"):
            continue
        gk = (r["duplicate_group_key"], r["subject_type"])
        visible_groups[gk] = visible_groups.get(gk, 0) + 1
    duplicate_inflation = sum(1 for n in visible_groups.values() if n > 1)

    project_review_hidden = 0  # by construction project_review_required is a visible state

    lifecycle_read_model_empty_with_candidates = (
        total_candidates > 0 and full["visible_count"] == 0 and state_counts.get("new", 0) > 0
    )

    # Defense-in-depth: the default review queue must never leak a hidden disposition as actionable.
    # By construction it cannot, but the gate verifies rather than trusts.
    leaks: set[str] = set()
    for r in visible_default_rows:
        st = r["lifecycle_state"]
        if st == lc.STATE_REJECTED:
            leaks.add("rejected_visible_as_new")
        elif st == lc.STATE_SUPPRESSED:
            leaks.add("suppressed_visible_as_new")
        elif st == lc.STATE_MERGED:
            leaks.add("merged_visible_as_new")
        elif st == lc.STATE_SNOOZED:
            leaks.add("snoozed_visible_before_return")

    contradictions = _contradictions(
        accepted_missing_source, coverage, duplicate_inflation,
        lifecycle_read_model_empty_with_candidates, actionable_total,
    )
    contradictions.extend(sorted(leaks))

    return {
        "generated_utc": now,
        "total_candidates": total_candidates,
        "visible_count": full["visible_count"],
        "hidden_count": full["hidden_count"],
        "state_counts": state_counts,
        "accepted_missing_source_count": accepted_missing_source,
        "actionable_source_ref_coverage": round(coverage, 4),
        "duplicate_inflation_groups": duplicate_inflation,
        "project_review_required_hidden": project_review_hidden,
        "lifecycle_read_model_empty_with_candidates": lifecycle_read_model_empty_with_candidates,
        "stage_failed": False,
        "contradictions": contradictions,
    }


def _contradictions(
    accepted_missing_source: int,
    coverage: float,
    duplicate_inflation: int,
    empty_with_candidates: bool,
    actionable_total: int,
) -> list[str]:
    out: list[str] = []
    if accepted_missing_source > 0:
        out.append("accepted_actions_missing_source_refs")
    if actionable_total > 0 and coverage < 1.0:
        out.append("lifecycle_source_ref_coverage_below_100")
    if duplicate_inflation > 0:
        out.append("duplicate_inflation")
    if empty_with_candidates:
        out.append("lifecycle_read_model_empty_with_candidates")
    return out


def render_daily_brief_lifecycle_markdown(view: dict[str, Any]) -> str:
    """Render a raw-safe markdown sample of the lifecycle view (bounded redacted titles only)."""
    sc = view["section_counts"]
    lines = [
        "# Daily Brief — Candidate Lifecycle View",
        "",
        f"_generated_utc: {view['generated_utc']}_",
        "",
        "## Section counts",
        "",
        f"- New review: {sc['new_review']}",
        f"- Accepted actions: {sc['accepted_actions']}",
        f"- User commitments: {sc['user_commitments']}",
        f"- Waiting on others: {sc['waiting_on_others']}",
        f"- Stale actions: {sc['stale_actions']}",
        f"- Project review required: {sc['project_review_required']}",
        f"- Source-missing withheld: {sc['source_missing_withheld']}",
        f"- Snoozed returning today: {view['snoozed_returning_count']}",
        "",
        "## Hidden from normal view (counts only)",
        "",
        f"- Rejected: {view['hidden_counts']['rejected']}"
        f" · Suppressed: {view['hidden_counts']['suppressed']}"
        f" · Merged: {view['hidden_counts']['merged']}"
        f" · Closed: {view['hidden_counts']['closed']}"
        f" · Snoozed (future): {view['hidden_counts']['snoozed_future']}",
        "",
        "## New review items",
        "",
    ]
    for r in view["sections"]["new_review"][:20]:
        title = r.get("title_redacted") or "(no title)"
        lines.append(
            f"- [{r['lifecycle_state']}] {title} "
            f"(project: {r.get('project_key') or 'review_required'}, "
            f"refs: {r['source_ref_count']})"
        )
    lines.append("")
    return "\n".join(lines) + "\n"
