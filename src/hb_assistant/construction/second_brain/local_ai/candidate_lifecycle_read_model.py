"""Phase 10 V50 — unified, deterministic, raw-safe candidate review queue read model.

Builds one row per candidate/action subject across all six families
(task/commitment candidates, daily-brief actions, accepted tasks/commitments, follow-up watch)
by joining the per-family tables with the V50 lifecycle overlay (events / merge links /
suppression rules). Every row follows ``references/review_queue_contract.md`` and contains only
already-redacted/bounded text, counts, hashes, ids, codes, and canonical states — never raw
content. Pure read; no writes. Backward-compatible: when the overlay tables are empty, rows fall
back to their per-family base state.
"""

from __future__ import annotations

from typing import Any, Optional

from . import candidate_lifecycle as lc
from .candidate_lifecycle_duplicates import duplicate_group_key

_TITLE_MAX = 120
_REASON_MAX = 240
_NEXT_ACTION_MAX = 160


def _safe(text: Optional[str], n: int) -> Optional[str]:
    """Defensively scrub (URLs/emails/tokens/HTML) then bound an already-redacted DB text field."""
    return lc.scrub_note(text, max_chars=n)


def _coverage_status(subject_type: str, count: Optional[int]) -> str:
    if count is None:
        return "not_applicable"
    if subject_type in lc.SOURCE_REQUIRED_SUBJECTS and count == 0:
        return "source_missing"
    return "ok" if count > 0 else "not_applicable"


def _project_resolution(subject_type: str, project_key: Optional[str], project_review: bool) -> str:
    if project_review:
        return "project_review_required"
    if project_key:
        return "resolved"
    return "unknown"


class _Index:
    """Precomputed overlay/source-ref indexes so the read model is a single pass, not O(n^2)."""

    def __init__(self, store: Any) -> None:
        self.overlays = store.latest_lifecycle_states()
        self.refs: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for r in store.list_candidate_source_refs(limit=1000000):
            key = (str(r.get("candidate_type")), str(r.get("candidate_id")))
            self.refs.setdefault(key, []).append(r)
        self.merge_sources: set[tuple[str, str]] = set()
        for link in store.list_merge_links():
            self.merge_sources.add(
                (str(link.get("source_subject_type")), str(link.get("source_subject_id")))
            )
        self.supp_candidates: set[tuple[str, str]] = set()
        self.supp_groups: set[str] = set()
        for rule in store.list_suppression_rules(active_only=True):
            if rule.get("scope") == "candidate":
                self.supp_candidates.add(
                    (str(rule.get("subject_type")), str(rule.get("subject_id")))
                )
            elif rule.get("scope") == "group" and rule.get("duplicate_group_key"):
                self.supp_groups.add(str(rule.get("duplicate_group_key")))
        # Candidate ids that already have an accepted_* row (the accepted row represents them).
        self.promoted_candidate_ids: set[str] = set()
        for a in store.list_accepted_tasks(limit=1000000):
            if a.get("candidate_id"):
                self.promoted_candidate_ids.add(str(a.get("candidate_id")))
        for a in store.list_accepted_commitments(limit=1000000):
            if a.get("candidate_id"):
                self.promoted_candidate_ids.add(str(a.get("candidate_id")))

    def refs_for(self, subject_type: str, subject_id: str) -> Optional[list[dict[str, Any]]]:
        resolved = lc.source_ref_candidate_id(subject_type, subject_id)
        if resolved is None:
            return None
        return self.refs.get(resolved, [])


def _row(
    idx: _Index,
    *,
    subject_type: str,
    subject_id: str,
    raw: dict[str, Any],
    base_state: str,
    family: str,
    now_utc: str,
) -> dict[str, Any]:
    refs = idx.refs_for(subject_type, subject_id)
    src_count = None if refs is None else len(refs)
    source_missing = subject_type in lc.SOURCE_REQUIRED_SUBJECTS and src_count == 0
    source_family = None
    if refs:
        source_family = str(refs[0].get("source_family") or "") or None

    overlay = idx.overlays.get((subject_type, subject_id))
    overlay_state = overlay.get("new_state") if overlay else None
    effective_until = overlay.get("effective_until_utc") if overlay else None

    disposition = overlay_state or base_state
    snoozed_future = False
    if disposition == lc.STATE_SNOOZED:
        if lc.is_future(effective_until, now_utc):
            snoozed_future = True
        else:
            disposition = lc.STATE_NEEDS_REVIEW

    project_key = raw.get("project_key")
    project_review = (
        subject_type in lc.PROJECT_LIKE_SUBJECTS
        and not project_key
        and not source_missing
    )
    group = duplicate_group_key(
        subject_type=subject_type,
        subject_id=subject_id,
        family=family,
        project_key=project_key,
        title_redacted=raw.get("title_redacted"),
        stable_key=raw.get("stable_key"),
        source_refs=refs or [],
    )
    suppressed = (subject_type, subject_id) in idx.supp_candidates or group in idx.supp_groups
    merged = (subject_type, subject_id) in idx.merge_sources

    state = lc.resolve_state(
        disposition,
        source_missing=source_missing,
        project_review_required=project_review,
        snoozed_future=snoozed_future,
        suppressed=suppressed,
        merged=merged,
    )
    hidden = state in lc.HIDDEN_FROM_BRIEF_STATES
    actionable = state in lc.ACTIONABLE_STATES
    promoted = (
        subject_type in ("task_candidate", "commitment_candidate")
        and subject_id in idx.promoted_candidate_ids
    )

    disposition_reason = overlay.get("reason_code") if overlay else None
    review_reason = None
    if state == lc.STATE_PROJECT_REVIEW_REQUIRED:
        review_reason = "missing_project_key"
    elif state == lc.STATE_SOURCE_MISSING:
        review_reason = "missing_source_refs"
    elif state == lc.STATE_NEEDS_REVIEW:
        review_reason = "low_confidence_or_unclear"

    return {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "candidate_id": raw.get("candidate_id") if subject_type not in (
            "task_candidate", "commitment_candidate"
        ) else subject_id,
        "family": family,
        "source_family": source_family,
        "title_redacted": _safe(raw.get("title_redacted"), _TITLE_MAX),
        "reason_redacted": _safe(raw.get("reason_redacted"), _REASON_MAX),
        "recommended_next_action_redacted": _safe(
            raw.get("recommended_next_action"), _NEXT_ACTION_MAX
        ),
        "confidence": raw.get("confidence"),
        "priority": raw.get("priority"),
        "project_key": project_key,
        "project_resolution_status": _project_resolution(subject_type, project_key, project_review),
        "source_ref_count": src_count if src_count is not None else 0,
        "source_ref_coverage_status": _coverage_status(subject_type, src_count),
        "candidate_status": raw.get("status"),
        "review_status": raw.get("review_status"),
        "accepted_status": raw.get("status") if subject_type in (
            "accepted_task", "accepted_commitment"
        ) else None,
        "watch_status": raw.get("watch_status"),
        "lifecycle_state": state,
        "duplicate_group_key": group,
        "age_bucket": lc.age_bucket(raw.get("created_utc"), now_utc),
        "due_bucket": lc.due_bucket(raw.get("due_at_utc"), now_utc),
        "review_reason": review_reason,
        "disposition_reason_code": disposition_reason,
        "hidden_from_daily_brief": hidden,
        "actionable": actionable,
        "promoted": promoted,
    }


def build_review_queue(
    store: Any,
    *,
    now_utc: Optional[str] = None,
    include_hidden: bool = False,
    limit_per_family: int = 100000,
) -> dict[str, Any]:
    """Build the unified review queue. Default view hides rejected/suppressed/merged/closed and
    future-snoozed rows; ``include_hidden=True`` returns every row with its state + reason."""
    now = now_utc or lc.utc_now()
    idx = _Index(store)
    rows: list[dict[str, Any]] = []

    for raw in store.list_task_candidates(limit=limit_per_family):
        sid = str(raw.get("candidate_id"))
        rows.append(_row(idx, subject_type="task_candidate", subject_id=sid, raw=raw,
                         base_state=lc.review_status_to_state(raw.get("review_status"),
                                                              raw.get("confidence")),
                         family="task", now_utc=now))
    for raw in store.list_commitment_candidates(limit=limit_per_family):
        sid = str(raw.get("candidate_id"))
        rows.append(_row(idx, subject_type="commitment_candidate", subject_id=sid, raw=raw,
                         base_state=lc.review_status_to_state(raw.get("review_status"),
                                                              raw.get("confidence")),
                         family="commitment", now_utc=now))
    for raw in store.list_daily_brief_action_candidates(limit=limit_per_family):
        sid = str(raw.get("daily_brief_action_candidate_id"))
        rows.append(_row(idx, subject_type="daily_brief_action", subject_id=sid, raw=raw,
                         base_state=lc.STATE_NEW, family=str(raw.get("section") or "actions"),
                         now_utc=now))
    for raw in store.list_accepted_tasks(limit=limit_per_family):
        sid = str(raw.get("accepted_task_id"))
        rows.append(_row(idx, subject_type="accepted_task", subject_id=sid, raw=raw,
                         base_state=lc.accepted_status_to_state(
                             raw.get("status"), raw.get("completed_utc"),
                             raw.get("accepted_utc"), now),
                         family="accepted_task", now_utc=now))
    for raw in store.list_accepted_commitments(limit=limit_per_family):
        sid = str(raw.get("accepted_commitment_id"))
        rows.append(_row(idx, subject_type="accepted_commitment", subject_id=sid, raw=raw,
                         base_state=lc.accepted_status_to_state(
                             raw.get("status"), raw.get("completed_utc"),
                             raw.get("accepted_utc"), now),
                         family="accepted_commitment", now_utc=now))
    for raw in store.list_follow_up_watch_items(limit=limit_per_family):
        sid = str(raw.get("watch_item_id"))
        rows.append(_row(idx, subject_type="follow_up_watch", subject_id=sid, raw=raw,
                         base_state=lc.watch_status_to_state(raw.get("watch_status")),
                         family="follow_up_watch", now_utc=now))

    # Default review queue = to-review states only, excluding promoted candidates (the accepted
    # row represents them). include_hidden returns every subject with its state + reason.
    visible = [
        r
        for r in rows
        if r["lifecycle_state"] in lc.REVIEW_QUEUE_DEFAULT_STATES
        and not (r["promoted"] and r["subject_type"] in ("task_candidate", "commitment_candidate"))
    ]
    selected = rows if include_hidden else visible
    selected.sort(key=lambda r: (r["lifecycle_state"], r["subject_type"], r["subject_id"]))

    state_counts: dict[str, int] = {}
    for r in rows:
        state_counts[r["lifecycle_state"]] = state_counts.get(r["lifecycle_state"], 0) + 1

    return {
        "generated_utc": now,
        "include_hidden": include_hidden,
        "total_subjects": len(rows),
        "visible_count": len(visible),
        "hidden_count": len(rows) - len(visible),
        "state_counts": state_counts,
        "rows": selected,
        "guardrails": {"raw_safe": True, "deterministic": True, "local_only": True},
    }
