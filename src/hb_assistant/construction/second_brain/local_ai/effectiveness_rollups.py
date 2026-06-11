"""Phase 10 V52 — raw-free effectiveness rollups.

Builds daily / window / project / candidate_family / source_family / model_profile rollups from an
effectiveness packet. All rollups are deterministic and raw-free; missing dimensions normalize to
``unknown`` so scope keys stay stable. Persistence is handled by the caller (apply only).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from . import daily_brief_effectiveness_metrics as M
from .daily_brief_effectiveness_packets import normalize_dim
from .procore_noise_evaluator import evaluate_procore_noise

# Rollup scope identifiers.
SCOPE_DAILY = "daily"
SCOPE_WINDOW = "window"
SCOPE_PROJECT = "project"
SCOPE_CANDIDATE_FAMILY = "candidate_family"
SCOPE_SOURCE_FAMILY = "source_family"
SCOPE_MODEL_PROFILE = "model_profile"


def _outcomes(items: list[dict[str, Any]]) -> list[str]:
    return [it["outcome_type"] for it in items if it.get("outcome_type")]


def _rank_outcome(items: list[dict[str, Any]]) -> Optional[float]:
    scored = [
        {"rank_position": it.get("rank_position") or 1, "outcome_type": it.get("outcome_type")}
        for it in items
    ]
    cc = max((int(it.get("rank_position") or 1) for it in items), default=len(items))
    return M.rank_outcome_score(scored, candidate_count=cc)


def _group_rollup(
    *,
    scope: str,
    scope_key: str,
    window_start: str,
    window_end: str,
    policy_version: Optional[str],
    items: list[dict[str, Any]],
    procore_noise: Optional[float],
    duplicate_proxy: Optional[float],
    feedback_lift: Optional[float],
) -> dict[str, Any]:
    outs = _outcomes(items)
    brief_count = len({it.get("brief_date") for it in items})
    coverage = M.source_ref_coverage(items)
    ros = _rank_outcome(items)
    low_noise = 1.0 - (procore_noise if procore_noise is not None else 0.0)
    usefulness = M.brief_usefulness_score(
        accepted_rate_value=M.accepted_rate(outs),
        rank_outcome_score_value=ros,
        source_ref_coverage_value=coverage,
        low_noise_component=low_noise,
        low_model_degradation_component=1.0,
        follow_through_component=M.accepted_rate(outs),
    )
    return {
        "scope": scope,
        "scope_key": scope_key,
        "window_start": window_start,
        "window_end": window_end,
        "policy_version": policy_version,
        "brief_count": brief_count,
        "candidate_count": len(items),
        "outcome_count": len(outs),
        "accepted_rate": M.accepted_rate(outs),
        "rejected_rate": M.rejected_rate(outs),
        "snoozed_rate": M.snoozed_rate(outs),
        "ignored_rate": M.ignored_rate(outs),
        "brief_usefulness_score": usefulness,
        "rank_outcome_score": ros,
        "source_ref_coverage": coverage,
        "procore_noise_score": procore_noise,
        "model_degradation_rate": None,
        "duplicate_precision_proxy": duplicate_proxy,
        "feedback_calibration_lift": feedback_lift,
        "sample_sufficient": len(outs) >= M.MIN_OUTCOME_SAMPLE,
    }


def build_rollups(
    packet: dict[str, Any], *, model_degradation_rate: Optional[float] = None
) -> list[dict[str, Any]]:
    """Build the full set of raw-free rollup rows for an effectiveness packet."""
    items = packet.get("items", [])
    window_start = packet["window_start"]
    window_end = packet["window_end"]
    policy_version = (
        str(packet["ranking_runs"][0].get("policy_version")) if packet.get("ranking_runs") else None
    )

    window_noise = evaluate_procore_noise(packet).get("procore_noise_score")
    reviewed_clusters = int(packet.get("similarity", {}).get("reviewed_clusters") or 0)
    merged = sum(1 for it in items if it.get("outcome_type") == M.MERGED)
    dup_proxy = M.duplicate_precision_proxy(merged, reviewed_clusters)["value"]
    feedback_lift = _feedback_calibration_lift(packet)

    rollups: list[dict[str, Any]] = []

    # Window-level rollup (carries duplicate proxy, feedback lift, model degradation).
    window_row = _group_rollup(
        scope=SCOPE_WINDOW,
        scope_key=f"{window_start}_{window_end}",
        window_start=window_start,
        window_end=window_end,
        policy_version=policy_version,
        items=items,
        procore_noise=window_noise,
        duplicate_proxy=dup_proxy,
        feedback_lift=feedback_lift,
    )
    window_row["model_degradation_rate"] = model_degradation_rate
    rollups.append(window_row)

    rollups.extend(
        _scoped(
            items,
            SCOPE_DAILY,
            lambda it: str(it.get("brief_date")),
            window_start,
            window_end,
            policy_version,
        )
    )
    rollups.extend(
        _scoped(
            items,
            SCOPE_PROJECT,
            lambda it: normalize_dim(it.get("project_key")),
            window_start,
            window_end,
            policy_version,
        )
    )
    rollups.extend(
        _scoped(
            items,
            SCOPE_CANDIDATE_FAMILY,
            lambda it: normalize_dim(it.get("candidate_family")),
            window_start,
            window_end,
            policy_version,
        )
    )
    rollups.extend(
        _scoped(
            items,
            SCOPE_SOURCE_FAMILY,
            lambda it: normalize_dim(it.get("source_family")),
            window_start,
            window_end,
            policy_version,
        )
    )
    rollups.extend(
        _scoped(
            items,
            SCOPE_MODEL_PROFILE,
            lambda it: normalize_dim(it.get("model_profile_id")),
            window_start,
            window_end,
            policy_version,
        )
    )
    return rollups


def _scoped(
    items: list[dict[str, Any]],
    scope: str,
    key_fn: Callable[[dict[str, Any]], str],
    window_start: str,
    window_end: str,
    policy_version: Optional[str],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        groups.setdefault(key_fn(it), []).append(it)
    rows: list[dict[str, Any]] = []
    for scope_key, g in sorted(groups.items()):
        rows.append(
            _group_rollup(
                scope=scope,
                scope_key=scope_key,
                window_start=window_start,
                window_end=window_end,
                policy_version=policy_version,
                items=g,
                procore_noise=None,
                duplicate_proxy=None,
                feedback_lift=None,
            )
        )
    return rows


def _feedback_calibration_lift(packet: dict[str, Any]) -> Optional[float]:
    """Calibrated-vs-prior-policy lift across policy versions present in the window.

    Returns ``None`` (insufficient) when fewer than two policy versions are observed — absent a
    prior baseline policy, a lift is not computed (no false signal).
    """
    runs = packet.get("ranking_runs", [])
    policies = sorted({str(r.get("policy_version")) for r in runs if r.get("policy_version")})
    if len(policies) < 2:
        return None
    items = packet.get("items", [])
    scores: dict[str, Optional[float]] = {}
    for pol in policies:
        pol_items = [it for it in items if str(it.get("policy_version")) == pol]
        scores[pol] = _rank_outcome(pol_items)
    baseline, calibrated = scores[policies[0]], scores[policies[-1]]
    result = M.feedback_calibration_lift(
        calibrated_policy_score=calibrated,
        baseline_policy_score=baseline,
        sample_size=len(_outcomes(items)),
    )
    return result["value"]
