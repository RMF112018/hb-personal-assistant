"""Phase 10 V52 — deterministic daily-brief effectiveness metric engine.

Pure, observational, raw-free metric functions over the effectiveness packets built by
``daily_brief_effectiveness_packets``. Every metric is deterministic with stable rounding; none
calls a model or reads raw content. Metrics that depend on operator feedback mark a small sample
as ``insufficient_sample`` and never treat absent feedback as success.

Formulas follow ``references/metric_definitions.md`` in the implementation package. These metrics
are advisory and observational — not causal — unless the repo later adds true A/B assignment.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

ROUND = 4

#: Minimum reviewed-outcome sample before a feedback-derived metric is considered sufficient.
MIN_OUTCOME_SAMPLE = 5
#: Minimum reviewed duplicate/similarity clusters before the precision proxy is sufficient.
MIN_DUPLICATE_CLUSTER_SAMPLE = 5
#: Minimum per-policy sample before a calibration-lift comparison is sufficient.
MIN_CALIBRATION_SAMPLE = 5
#: Default lag window (hours) after which an exposed, un-actioned item is called ``ignored``.
DEFAULT_IGNORED_LAG_HOURS = 72

# Canonical outcome types derived from the V50 lifecycle read model (never inferred from rank).
ACCEPTED = "accepted"
REJECTED = "rejected"
SNOOZED = "snoozed"
IGNORED = "ignored"
MERGED = "merged"
SUPPRESSED = "suppressed"
CLOSED = "closed"
REOPENED = "reopened"
STALE_NO_ACTION = "stale_no_action"

#: Default observational outcome weights (``references/metric_definitions.md``).
OUTCOME_WEIGHTS: dict[str, float] = {
    ACCEPTED: 1.0,
    CLOSED: 1.0,
    REOPENED: 0.2,
    SNOOZED: 0.1,
    STALE_NO_ACTION: -0.2,
    IGNORED: -0.4,
    REJECTED: -0.8,
    SUPPRESSED: -0.9,
    MERGED: -0.3,
}

#: Outcomes that count as a positive operator action (numerator for adoption proxies).
POSITIVE_OUTCOMES = frozenset({ACCEPTED, CLOSED, REOPENED, SNOOZED})


def outcome_weight(outcome_type: Optional[str]) -> float:
    """Return the observational weight for an outcome type (0.0 for unknown/None)."""
    if not outcome_type:
        return 0.0
    return OUTCOME_WEIGHTS.get(outcome_type, 0.0)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round(value: float) -> float:
    return round(value, ROUND)


def _rate(count: int, total: int) -> float:
    """Deterministic rate; 0.0 when there is no eligible denominator."""
    if total <= 0:
        return 0.0
    return _round(count / total)


def accepted_rate(outcomes: Iterable[str]) -> float:
    outs = list(outcomes)
    return _rate(sum(1 for o in outs if o == ACCEPTED), len(outs))


def rejected_rate(outcomes: Iterable[str]) -> float:
    outs = list(outcomes)
    return _rate(sum(1 for o in outs if o == REJECTED), len(outs))


def snoozed_rate(outcomes: Iterable[str]) -> float:
    outs = list(outcomes)
    return _rate(sum(1 for o in outs if o == SNOOZED), len(outs))


def ignored_rate(outcomes: Iterable[str]) -> float:
    """Exposed items with no lifecycle movement after the lag window / eligible exposed items.

    Absent feedback is never treated as acceptance; it is only counted as ``ignored`` once the
    configured lag window (default 72h) has elapsed, which the packet builder encodes upstream.
    """
    outs = list(outcomes)
    return _rate(sum(1 for o in outs if o == IGNORED), len(outs))


def stale_accepted_recurrence(stale_accepted_resurfaced: int, accepted_resurfaced: int) -> float:
    return _rate(stale_accepted_resurfaced, accepted_resurfaced)


def rank_outcome_score(
    items: list[dict[str, Any]], candidate_count: Optional[int] = None
) -> Optional[float]:
    """Normalized mean of ``outcome_weight * rank_weight`` over evaluated items, mapped to 0..1.

    ``rank_weight = 1 - ((rank_position - 1) / max(candidate_count - 1, 1))`` so accepted items that
    rank higher raise the score and rejected/ignored items that rank higher lower it. Returns
    ``None`` when there are no items carrying an outcome.
    """
    scored = [it for it in items if it.get("outcome_type")]
    if not scored:
        return None
    n = candidate_count if candidate_count is not None else len(items)
    denom = max(n - 1, 1)
    raw_scores: list[float] = []
    for it in scored:
        rank_position = int(it.get("rank_position") or 1)
        rank_weight = 1.0 - ((rank_position - 1) / denom)
        raw_scores.append(outcome_weight(it.get("outcome_type")) * rank_weight)
    mean = sum(raw_scores) / len(raw_scores)
    # Map weighted mean (theoretically in [-0.9, 1.0]) to 0..1 around the [-1, 1] envelope.
    return _round(_clamp01((mean + 1.0) / 2.0))


def source_family_usefulness_score(
    *,
    accepted_rate_value: float,
    source_ref_coverage_value: float,
    closed_or_progressed_rate: float,
    rejected_rate_value: float,
    ignored_rate_value: float,
) -> float:
    """Weighted usefulness for a candidate/source family, clamped to 0..1."""
    score = (
        0.45 * accepted_rate_value
        + 0.20 * source_ref_coverage_value
        + 0.15 * closed_or_progressed_rate
        - 0.10 * rejected_rate_value
        - 0.10 * ignored_rate_value
    )
    return _round(_clamp01(score))


def procore_noise_score(
    *,
    exposed_procore: int,
    rejected: int,
    ignored: int,
    suppressed: int,
    false_duplicate_proxy: int = 0,
    top_rank_noisy: int = 0,
) -> Optional[float]:
    """Procore clutter/noise score. Higher = noisier. ``None`` when no Procore items were exposed.

    A rank-weighted penalty adds weight when noisy items appeared in top ranks. The score is a
    tuning/review signal only — it never suppresses or re-thresholds anything.
    """
    if exposed_procore <= 0:
        return None
    base = (rejected + ignored + suppressed + false_duplicate_proxy) / exposed_procore
    rank_penalty = (top_rank_noisy / exposed_procore) * 0.25
    return _round(_clamp01(base + rank_penalty))


def model_advice_validity_rate(valid: int, attempts: int) -> Optional[float]:
    if attempts <= 0:
        return None
    return _round(valid / attempts)


def advisory_adoption_proxy(
    positively_acted_with_advice: int, positively_acted_total: int
) -> Optional[float]:
    """Proxy (not causation) for whether model advice accompanied positive operator actions."""
    if positively_acted_total <= 0:
        return None
    return _round(positively_acted_with_advice / positively_acted_total)


def model_degradation_rate(degraded_runs: int, total_runs: int) -> Optional[float]:
    """Ranking/model runs with degraded/withheld/fallback/timeout/invalid/unsafe status / total."""
    if total_runs <= 0:
        return None
    return _round(degraded_runs / total_runs)


def duplicate_precision_proxy(merged_as_duplicate: int, reviewed_clusters: int) -> dict[str, Any]:
    """Advised clusters later merged/suppressed as duplicate / reviewed advised clusters.

    Marked ``insufficient_sample`` below ``MIN_DUPLICATE_CLUSTER_SAMPLE`` reviewed clusters.
    """
    insufficient = reviewed_clusters < MIN_DUPLICATE_CLUSTER_SAMPLE
    value = None if reviewed_clusters <= 0 else _round(merged_as_duplicate / reviewed_clusters)
    return {
        "value": value,
        "sample_size": reviewed_clusters,
        "insufficient_sample": insufficient,
    }


def source_ref_coverage(items: list[dict[str, Any]]) -> float:
    """Surfaced actionable items with source_ref_count > 0 / surfaced actionable items.

    Coverage below 1.0 is reported honestly (the caller degrades per the source-ref gate). When
    there are no surfaced actionable items, coverage is trivially 1.0.
    """
    actionable = [it for it in items if it.get("actionable")]
    if not actionable:
        return 1.0
    covered = sum(1 for it in actionable if int(it.get("source_ref_count") or 0) > 0)
    return _round(covered / len(actionable))


def brief_usefulness_score(
    *,
    accepted_rate_value: float,
    rank_outcome_score_value: Optional[float],
    source_ref_coverage_value: float,
    low_noise_component: float,
    low_model_degradation_component: float,
    follow_through_component: float,
) -> float:
    """Deterministic blended usefulness score, clamped to 0..1. ``None`` rank-outcome → 0.0 term."""
    ros = rank_outcome_score_value if rank_outcome_score_value is not None else 0.0
    score = (
        0.30 * accepted_rate_value
        + 0.20 * ros
        + 0.20 * source_ref_coverage_value
        + 0.10 * _clamp01(low_noise_component)
        + 0.10 * _clamp01(low_model_degradation_component)
        + 0.10 * _clamp01(follow_through_component)
    )
    return _round(_clamp01(score))


def deterministic_vs_model_delta(
    model_assisted_score: Optional[float], deterministic_baseline_score: Optional[float]
) -> dict[str, Any]:
    """Observed (non-causal) difference model_assisted - deterministic_baseline."""
    if model_assisted_score is None or deterministic_baseline_score is None:
        return {"value": None, "causal": False, "note": "baseline_or_model_score_unavailable"}
    return {
        "value": _round(model_assisted_score - deterministic_baseline_score),
        "causal": False,
        "note": "observational_only_no_ab_assignment",
    }


def feedback_calibration_lift(
    *,
    calibrated_policy_score: Optional[float],
    baseline_policy_score: Optional[float],
    sample_size: int,
) -> dict[str, Any]:
    """Observed score difference calibrated - baseline, with a small-sample insufficiency flag."""
    insufficient = sample_size < MIN_CALIBRATION_SAMPLE
    if calibrated_policy_score is None or baseline_policy_score is None:
        return {
            "value": None,
            "sample_size": sample_size,
            "insufficient_sample": insufficient,
            "note": "baseline_unavailable",
        }
    return {
        "value": _round(calibrated_policy_score - baseline_policy_score),
        "sample_size": sample_size,
        "insufficient_sample": insufficient,
        "note": "observational_only" if not insufficient else "insufficient_sample",
    }


def metric_with_sufficiency(
    value: Optional[float], sample_size: int, threshold: int = MIN_OUTCOME_SAMPLE
) -> dict[str, Any]:
    """Wrap a metric value with a deterministic small-sample flag."""
    return {
        "value": value,
        "sample_size": sample_size,
        "insufficient_sample": sample_size < threshold,
    }
