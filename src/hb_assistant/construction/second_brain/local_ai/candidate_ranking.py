"""Phase 10 V51 — deterministic candidate ranking engine (authoritative; model is advisory).

Scores each packet candidate on a 0..100 deterministic base from lifecycle state, due proximity,
waiting state, family/section risk, project identity, source-ref strength, and confidence, then
penalises deterministic duplicate copies. Feedback calibration (bounded, aggregate) and an optional
bounded model advisory score are blended in:

    final = 0.75*deterministic + 0.20*feedback + 0.05*model        (model present)
    final = 0.80*deterministic + 0.20*feedback                     (model absent/withheld)

The model is **bounded**: no candidate may move more than ``MAX_RANK_MOVEMENT`` positions away from
its deterministic-only rank. Because deterministic-close candidates sit at adjacent deterministic
ranks, the model can freely reorder them (small moves) but can never leapfrog a clearly-higher
deterministic candidate. Ordering ties break deterministically:
final ↓ → deterministic ↓ → lifecycle priority → due bucket → project_key → candidate id.

Pure and deterministic: no clock, no randomness, no DB, no network.
"""

from __future__ import annotations

from typing import Any, Optional

from . import candidate_lifecycle as lc
from .feedback_calibration import feedback_score_for_family

POLICY_VERSION = "rank-policy-v1"
ALGORITHM_VERSION = "rank-det-v1"

#: The model may move a candidate at most this many positions from its deterministic-only rank.
MAX_RANK_MOVEMENT = 3
#: Deterministic scores within this fraction (0..1 scale) are "close" — the model may reorder them.
DET_CLOSE_THRESHOLD = 0.08

_BASE_SCORE = 50.0

_LIFECYCLE_BOOST: dict[str, float] = {
    lc.STATE_STALE: 14.0,
    lc.STATE_ACCEPTED: 10.0,
    lc.STATE_NEEDS_REVIEW: 4.0,
    lc.STATE_PROJECT_REVIEW_REQUIRED: 2.0,
    lc.STATE_NEW: 0.0,
}
_DUE_BOOST: dict[str, float] = {
    "overdue": 18.0,
    "today": 14.0,
    "next_3d": 10.0,
    "next_7d": 5.0,
    "future": 1.0,
    "none": 0.0,
    "unknown": 0.0,
}
#: Lower rank = higher precedence in deterministic tie-breaking.
_LIFECYCLE_TIE_RANK: dict[str, int] = {
    lc.STATE_STALE: 0,
    lc.STATE_ACCEPTED: 1,
    lc.STATE_PROJECT_REVIEW_REQUIRED: 2,
    lc.STATE_NEEDS_REVIEW: 3,
    lc.STATE_NEW: 4,
}
_DUE_TIE_RANK: dict[str, int] = {
    "overdue": 0,
    "today": 1,
    "next_3d": 2,
    "next_7d": 3,
    "future": 4,
    "unknown": 5,
    "none": 6,
}
_RISK_SECTIONS: frozenset[str] = frozenset({"procore"})
_MEETING_SECTIONS: frozenset[str] = frozenset({"calendar", "meeting_prep"})


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def deterministic_score(item: dict[str, Any], *, duplicate_primary: bool = True) -> float:
    """Compute the 0..100 deterministic base score for a packet item dict."""
    score = _BASE_SCORE
    score += _LIFECYCLE_BOOST.get(str(item.get("lifecycle_state")), 0.0)
    score += _DUE_BOOST.get(str(item.get("due_bucket") or "none"), 0.0)

    if str(item.get("waiting_signal")) == "waiting_on_others":
        score += 6.0  # a stale/awaited response needs a nudge

    section = str(item.get("section") or "")
    family = str(item.get("family") or "")
    if section in _RISK_SECTIONS or family in _RISK_SECTIONS:
        score += 6.0  # project / Procore risk
    if (section in _MEETING_SECTIONS or family in _MEETING_SECTIONS) and str(
        item.get("due_bucket")
    ) in ("today", "next_3d"):
        score += 6.0  # imminent meeting prep

    if item.get("project_key"):
        score += 4.0  # project-linked beats unlinked when otherwise tied

    refs = int(item.get("source_ref_count") or 0)
    if refs >= 2:
        score += 3.0
    elif refs == 1:
        score += 1.0

    confidence = item.get("confidence")
    if confidence is not None:
        score += float(confidence) * 6.0

    if not duplicate_primary:
        score -= 10.0  # a deterministic duplicate copy is not its own top priority

    return round(_clamp(score), 4)


def blend_scores(
    det: float, feedback: float, model: Optional[float]
) -> float:
    """Blend the deterministic, feedback, and (optional) model scores into the 0..100 final score."""
    if model is None:
        return round(_clamp(0.80 * det + 0.20 * feedback), 4)
    return round(_clamp(0.75 * det + 0.20 * feedback + 0.05 * model), 4)


def _duplicate_primaries(items: list[dict[str, Any]]) -> set[str]:
    """Pick one primary per deterministic duplicate group; the rest are penalised copies."""
    primary: dict[str, str] = {}
    for it in items:
        gk = item_group(it)
        if gk is None:
            continue
        cid = str(it["candidate_id"])
        if gk not in primary or cid < primary[gk]:
            primary[gk] = cid
    return set(primary.values())


def item_group(item: dict[str, Any]) -> Optional[str]:
    gk = item.get("duplicate_group_key")
    return str(gk) if gk else None


def _tie_key(item: dict[str, Any]) -> tuple[int, int, str, str]:
    return (
        _LIFECYCLE_TIE_RANK.get(str(item.get("lifecycle_state")), 9),
        _DUE_TIE_RANK.get(str(item.get("due_bucket") or "none"), 9),
        str(item.get("project_key") or "~"),  # linked (real keys) sort before unlinked "~"
        str(item.get("candidate_id")),
    )


def rank_candidates(
    items: list[dict[str, Any]],
    *,
    calibration: dict[str, Any],
    model_scores: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """Rank packet items deterministically, blending bounded feedback + optional model advice.

    ``items`` are raw-free packet-item dicts. ``model_scores`` maps candidate_id → 0..100 advisory
    score (already validated/bounded by the advisory layer); ``None`` means no model influence.
    Returns ranked dicts with all component scores and a 1-based ``rank_position``.
    """
    if not items:
        return []
    primaries = _duplicate_primaries(items)
    model_scores = model_scores or {}

    scored: list[dict[str, Any]] = []
    for it in items:
        cid = str(it["candidate_id"])
        det = deterministic_score(it, duplicate_primary=cid in primaries)
        fb = feedback_score_for_family(it.get("family"), calibration)
        model = model_scores.get(cid)
        final = blend_scores(det, fb, model)
        scored.append(
            {
                **it,
                "deterministic_score": det,
                "feedback_score": round(fb, 4),
                "model_advisory_score": (round(model, 4) if model is not None else None),
                "final_score": final,
            }
        )

    # Deterministic-only baseline ranks (det desc, then tie-breakers).
    det_sorted = sorted(scored, key=lambda r: (-r["deterministic_score"], _tie_key(r)))
    det_rank = {str(r["candidate_id"]): i for i, r in enumerate(det_sorted)}

    # Blended tentative ranks (final desc, then tie-breakers).
    blended_sorted = sorted(scored, key=lambda r: (-r["final_score"], _tie_key(r)))
    blended_rank = {str(r["candidate_id"]): i for i, r in enumerate(blended_sorted)}

    # Bound model displacement: clamp each item within ±MAX_RANK_MOVEMENT of its deterministic rank.
    # Deterministic-close items already sit at adjacent ranks, so they reorder freely; a clearly
    # higher-deterministic item can never be leapfrogged by more than the bounded influence.
    def _bounded_key(r: dict[str, Any]) -> tuple[int, int, tuple[int, int, str, str]]:
        cid = str(r["candidate_id"])
        dr = det_rank[cid]
        bounded = min(max(blended_rank[cid], dr - MAX_RANK_MOVEMENT), dr + MAX_RANK_MOVEMENT)
        return (bounded, dr, _tie_key(r))

    final_sorted = sorted(scored, key=_bounded_key)
    for position, r in enumerate(final_sorted, start=1):
        r["rank_position"] = position
    return final_sorted
