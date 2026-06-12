"""Phase 10 V51 — candidate ranking packet builder (deterministic, raw-free, source-gated).

Consumes the V50 unified review-queue read model (the authoritative, raw-safe join of every
candidate family with lifecycle/merge/suppression overlay) and turns the operator-relevant,
*non-hidden* subjects for a brief date into a deterministic packet for the ranking engine and the
bounded advisory model.

Hard gates enforced here (see the design contract):

* Lifecycle exclusions are authoritative — rejected / suppressed / merged-away / closed /
  future-snoozed rows never enter the packet (the read model already hides them).
* Source-ref coverage is non-negotiable — actionable, source-required subjects that are
  ``source_missing`` are **withheld** (never ranked as surfaced) and counted, and the run is
  marked degraded. The packet's surfaced source-ref coverage is therefore always 1.0.
* Raw safety — every text field is re-scanned with the shared forbidden-token scanner; any hit
  fails the packet closed (``packet_guard_clean=False``) rather than rendering.
* Honesty — an empty eligible set returns ``no_eligible_candidates`` (not success theatre).

No model call, no writeback, no raw content. Only redacted titles/reasons, counts, hashes, ids,
buckets, and canonical states move.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from . import candidate_lifecycle as lc
from .candidate_lifecycle_feedback import build_feedback_summary
from .candidate_lifecycle_read_model import build_review_queue
from .candidate_ranking_models import CandidateRankingPacket, CandidateRankingPacketItem
from .model_eval_metrics import scan_text_for_forbidden

#: Families/sections that imply a "waiting on others" signal (deterministic, bounded heuristic).
_WAITING_SECTIONS: frozenset[str] = frozenset({"waiting", "waiting_on_others"})
#: Subjects that must trace to >=1 source ref to be surfaced honestly (candidates via the read-model
#: source-missing state; accepted subjects via the accepted-missing-source contradiction).
_MUST_HAVE_REFS: frozenset[str] = frozenset(
    set(lc.SOURCE_REQUIRED_SUBJECTS) | {"accepted_task", "accepted_commitment"}
)


def _waiting_signal(subject_type: str, family: str, section: str, explicit: str) -> str:
    """Resolve a waiting signal, preferring an explicit accepted/candidate ``waiting_state``."""
    if explicit in ("waiting_on_me", "waiting_on_others"):
        return explicit
    if subject_type == "follow_up_watch":
        return "waiting_on_others"
    if family in _WAITING_SECTIONS or section in _WAITING_SECTIONS:
        return "waiting_on_others"
    return "unknown"


def _waiting_state_index(store: Any) -> dict[str, str]:
    """Map accepted/candidate subject_id → its explicit waiting_state (raw-free; additive join).

    The V50 review-queue row collapses ``waiting_state`` to a family label, so V51 re-joins the
    per-family tables to recover the explicit waiting signal without modifying the read model.
    """
    index: dict[str, str] = {}
    for row in store.list_accepted_tasks(limit=1000000):
        index[str(row.get("accepted_task_id"))] = str(row.get("waiting_state") or "unknown")
    for row in store.list_accepted_commitments(limit=1000000):
        index[str(row.get("accepted_commitment_id"))] = str(row.get("waiting_state") or "unknown")
    for row in store.list_task_candidates(limit=1000000):
        index[str(row.get("candidate_id"))] = str(row.get("waiting_state") or "unknown")
    for row in store.list_commitment_candidates(limit=1000000):
        index[str(row.get("candidate_id"))] = str(row.get("waiting_state") or "unknown")
    return index


def _is_visible(row: dict[str, Any]) -> bool:
    """The operator still has work to do on this subject (mirrors the lifecycle daily-brief view)."""
    if row.get("hidden_from_daily_brief"):
        return False
    return not (
        row.get("promoted") and row["subject_type"] in ("task_candidate", "commitment_candidate")
    )


def _row_text_fields(row: dict[str, Any]) -> list[str]:
    return [
        str(row.get("title_redacted") or ""),
        str(row.get("reason_redacted") or ""),
        str(row.get("recommended_next_action_redacted") or ""),
    ]


def _candidate_id(row: dict[str, Any]) -> str:
    """Canonical, stable ranking candidate id for a review-queue subject.

    A daily-brief action subject keeps its ``dbac-…`` id; every other family is namespaced by its
    subject type so accepted tasks, watch items, and candidates never collide.
    """
    subject_type = str(row["subject_type"])
    subject_id = str(row["subject_id"])
    if subject_type == "daily_brief_action":
        return subject_id
    return f"{subject_type}:{subject_id}"


def build_candidate_ranking_packet(
    store: Any, *, brief_date: str, now_utc: Optional[str] = None
) -> dict[str, Any]:
    """Build the deterministic ranking packet for ``brief_date``.

    Returns a dict with ``status`` in {``ok``, ``no_eligible_candidates``, ``fail_closed``}, the
    raw-free ``packet`` (a :class:`CandidateRankingPacket` dump), the withheld source-missing
    count, and the alias→candidate-id map. Never raises on empty/edge cases — it reports honestly.
    """
    now = now_utc or lc.utc_now()
    queue = build_review_queue(store, now_utc=now, include_hidden=True)
    rows = [r for r in queue["rows"] if _is_visible(r)]

    # Withhold source-missing actionable subjects (they lack the non-negotiable source refs). They
    # are counted and reported, never ranked as surfaced — exactly like the lifecycle brief view.
    withheld = [r for r in rows if r["lifecycle_state"] == lc.STATE_SOURCE_MISSING]
    eligible = [r for r in rows if r["lifecycle_state"] != lc.STATE_SOURCE_MISSING]

    # Deterministic alias order: section, then priority asc, then candidate id.
    eligible.sort(
        key=lambda r: (
            str(r.get("family") or ""),
            int(r.get("priority") or 100),
            _candidate_id(r),
        )
    )

    # Defence-in-depth raw scan over every text field that could reach the model or an artifact.
    leak_categories: set[str] = set()
    for r in rows:
        for text in _row_text_fields(r):
            leak_categories.update(scan_text_for_forbidden(text))

    waiting_index = _waiting_state_index(store)
    items: list[CandidateRankingPacketItem] = []
    alias_map: dict[str, str] = {}
    char_count = 0
    for i, r in enumerate(eligible, start=1):
        alias = f"c{i}"
        cid = _candidate_id(r)
        alias_map[alias] = cid
        subject_type = str(r["subject_type"])
        family = str(r.get("family") or "")
        section = str(r.get("family") or "actions")
        title = r.get("title_redacted")
        reason = r.get("reason_redacted")
        char_count += len(str(title or "")) + len(str(reason or ""))
        explicit_waiting = waiting_index.get(str(r.get("subject_id")), "unknown")
        items.append(
            CandidateRankingPacketItem(
                alias=alias,
                candidate_id=cid,
                subject_type=subject_type,
                family=family,
                section=section,
                title_redacted=title,
                reason_redacted=reason,
                project_key=r.get("project_key"),
                lifecycle_state=str(r["lifecycle_state"]),
                due_bucket=str(r.get("due_bucket") or "none"),
                age_bucket=str(r.get("age_bucket") or "unknown"),
                waiting_signal=_waiting_signal(subject_type, family, section, explicit_waiting),
                confidence=r.get("confidence"),
                source_ref_count=int(r.get("source_ref_count") or 0),
                source_ref_coverage_status=str(r.get("source_ref_coverage_status") or "not_applicable"),
                duplicate_group_key=r.get("duplicate_group_key"),
                actionable=bool(r.get("actionable")),
            )
        )

    # Surfaced source-ref coverage is computed over every surfaced subject that MUST trace to a
    # source ref (source-required candidates + accepted tasks/commitments). Withheld source-missing
    # candidates are excluded from the surface; an accepted item lacking refs lowers coverage and
    # degrades the run (mirrors the lifecycle ``accepted_actions_missing_source_refs`` contradiction).
    surfaced_required = [it for it in items if it.subject_type in _MUST_HAVE_REFS]
    covered = sum(1 for it in surfaced_required if it.source_ref_count > 0)
    coverage = (covered / len(surfaced_required)) if surfaced_required else 1.0

    candidate_set_hash = _candidate_set_hash(items)
    feedback_summary = build_feedback_summary(store, now_utc=now)
    feedback_digest_hash = _feedback_digest_hash(feedback_summary)

    guard_clean = not leak_categories
    packet = CandidateRankingPacket(
        brief_date=brief_date,
        items=items,
        candidate_set_hash=candidate_set_hash,
        feedback_digest_hash=feedback_digest_hash,
        packet_char_count=char_count,
        source_ref_coverage=round(coverage, 4),
        packet_guard_clean=guard_clean,
    )

    if not guard_clean:
        status = "fail_closed"
    elif not items:
        status = "no_eligible_candidates"
    else:
        status = "ok"

    return {
        "status": status,
        "brief_date": brief_date,
        "generated_utc": now,
        "packet": packet.model_dump(),
        "alias_map": alias_map,
        "withheld_source_missing_count": len(withheld),
        "leak_categories": sorted(leak_categories),
        "feedback_summary": feedback_summary,
    }


def _candidate_set_hash(items: list[CandidateRankingPacketItem]) -> str:
    """Stable hash over the eligible candidate set (id + state + key deterministic signals)."""
    payload = [
        [
            it.candidate_id,
            it.lifecycle_state,
            it.section,
            it.due_bucket,
            it.project_key or "",
            it.source_ref_count,
        ]
        for it in sorted(items, key=lambda x: x.candidate_id)
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "cs:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _feedback_digest_hash(summary: dict[str, Any]) -> str:
    """Stable hash over the raw-free feedback digest (counts/rates/codes only — no raw text)."""
    digest = {
        "counts": summary.get("counts"),
        "acceptance_rate_by_family": summary.get("acceptance_rate_by_family"),
        "by_family": summary.get("by_family"),
        "reason_codes": summary.get("reason_codes"),
        "confidence_buckets": summary.get("confidence_buckets"),
    }
    blob = json.dumps(digest, sort_keys=True, separators=(",", ":"))
    return "fd:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]
