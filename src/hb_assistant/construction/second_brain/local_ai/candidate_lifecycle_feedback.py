"""Phase 10 V50 — raw-safe feedback read model for future extractor/ranking improvement.

Derives a deterministic summary from the unified lifecycle read model + the append-only event
log: acceptance/rejection/snooze/merge/suppression patterns, reason-code distributions, confidence
buckets, duplicate-group counts, and project resolution. Read-only; emits only counts, codes,
buckets, and group keys (hashes) — never raw text, bodies, URLs, recipients, or model prompts.
See ``references/feedback_read_model_contract.md``.
"""

from __future__ import annotations

from typing import Any, Optional

from . import candidate_lifecycle as lc
from .candidate_lifecycle_read_model import build_review_queue

_CONFIDENCE_BUCKETS = ("0_25", "26_50", "51_70", "71_85", "86_100", "unknown")


def _confidence_bucket(confidence: Optional[float]) -> str:
    if confidence is None:
        return "unknown"
    pct = confidence * 100 if confidence <= 1.0 else confidence
    if pct <= 25:
        return "0_25"
    if pct <= 50:
        return "26_50"
    if pct <= 70:
        return "51_70"
    if pct <= 85:
        return "71_85"
    return "86_100"


def _bump(d: dict[str, int], key: Optional[str]) -> None:
    k = key or "unknown"
    d[k] = d.get(k, 0) + 1


def build_feedback_summary(store: Any, *, now_utc: Optional[str] = None) -> dict[str, Any]:
    """Build the deterministic, raw-safe feedback summary across all candidate families."""
    now = now_utc or lc.utc_now()
    queue = build_review_queue(store, now_utc=now, include_hidden=True)
    rows = queue["rows"]

    counts = {
        "total_reviewed": 0,
        "accepted": 0,
        "rejected": 0,
        "snoozed": 0,
        "merged": 0,
        "suppressed": 0,
        "closed": 0,
        "project_review_required": 0,
        "source_missing": 0,
        "needs_review": 0,
        "stale": 0,
        "new": 0,
    }
    by_family: dict[str, int] = {}
    by_source_family: dict[str, int] = {}
    confidence_buckets: dict[str, int] = dict.fromkeys(_CONFIDENCE_BUCKETS, 0)
    project_resolution: dict[str, int] = {}
    group_members: dict[str, int] = {}

    def _is_promoted_candidate(row: dict[str, Any]) -> bool:
        # A promoted task/commitment candidate is the same item as its accepted_* row; count it
        # once (via the accepted row) so disposition outcomes are not inflated.
        return bool(row.get("promoted")) and row["subject_type"] in (
            "task_candidate", "commitment_candidate"
        )

    rows = [r for r in rows if not _is_promoted_candidate(r)]

    for r in rows:
        state = r["lifecycle_state"]
        if state in counts:
            counts[state] += 1
        if state in (lc.STATE_ACCEPTED, lc.STATE_REJECTED, lc.STATE_SNOOZED, lc.STATE_MERGED,
                     lc.STATE_SUPPRESSED, lc.STATE_CLOSED):
            counts["total_reviewed"] += 1
        _bump(by_family, r.get("family"))
        _bump(by_source_family, r.get("source_family"))
        confidence_buckets[_confidence_bucket(r.get("confidence"))] += 1
        _bump(project_resolution, r.get("project_resolution_status"))
        group_members[r["duplicate_group_key"]] = group_members.get(r["duplicate_group_key"], 0) + 1

    # rejection / disposition reason distribution from the append-only event log (codes only).
    reason_codes: dict[str, int] = {}
    for ev in store.list_lifecycle_events(limit=1000000):
        if ev.get("reason_code"):
            _bump(reason_codes, f"{ev.get('event_type')}:{ev.get('reason_code')}")

    duplicate_groups = {
        "total_groups": len(group_members),
        "groups_with_duplicates": sum(1 for n in group_members.values() if n > 1),
        "max_group_size": max(group_members.values()) if group_members else 0,
    }

    acceptance_rate_by_family: dict[str, float] = {}
    accepted_by_family: dict[str, int] = {}
    for r in rows:
        if r["lifecycle_state"] == lc.STATE_ACCEPTED:
            accepted_by_family[r["family"]] = accepted_by_family.get(r["family"], 0) + 1
    for fam, total in by_family.items():
        acceptance_rate_by_family[fam] = round(accepted_by_family.get(fam, 0) / total, 4) if total else 0.0

    return {
        "generated_utc": now,
        "counts": counts,
        "by_family": dict(sorted(by_family.items())),
        "by_source_family": dict(sorted(by_source_family.items())),
        "acceptance_rate_by_family": dict(sorted(acceptance_rate_by_family.items())),
        "reason_codes": dict(sorted(reason_codes.items())),
        "confidence_buckets": confidence_buckets,
        "duplicate_groups": duplicate_groups,
        "project_resolution": dict(sorted(project_resolution.items())),
        "guardrails": {"raw_safe": True, "deterministic": True, "local_only": True},
    }
