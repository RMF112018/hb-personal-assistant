"""Phase 10 V52 — ranking-policy evaluator (observational only).

Evaluates how a ranking policy performed over a brief-date window, in four modes:

- ``observed`` — the persisted (final-score) ranking, as the operator saw it.
- ``deterministic-replay`` — re-rank by the deterministic score only (the model-free baseline).
- ``model-assisted-observed`` — the persisted ranking that included the bounded model nudge.
- ``ablation`` — both of the above plus their delta.

No model is ever called; model metadata is used only when already present in the packet. Metrics
carry sample-size caveats. Apply persistence (eval run + items) is handled by the caller, capped by
``--max-persist``. Advisory and observational only — never causal, never a mutation.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from . import daily_brief_effectiveness_metrics as M
from .daily_brief_effectiveness_packets import normalize_dim
from .procore_noise_evaluator import evaluate_procore_noise

EVAL_MODES = ("observed", "deterministic-replay", "model-assisted-observed", "ablation")

RANKING_ALGORITHM_VERSION = "rank-det-v1"
ASSEMBLY_POLICY_VERSION = "assembly-v1"


def _item_key(it: dict[str, Any]) -> tuple[str, str]:
    """Composite identity for a surfaced item: a candidate can recur across ranking runs."""
    return (
        str(it.get("ranking_run_id")),
        str(it.get("daily_brief_action_candidate_id")),
    )


def _rerank_positions(items: list[dict[str, Any]], score_key: str) -> dict[tuple[str, str], int]:
    """Return ``(ranking_run_id, candidate_id) -> 1-based rank`` by ``score_key`` desc within each run.

    Keyed by the composite (run, candidate) identity so the same candidate ranked in two ranking runs
    keeps a distinct position per run. Deterministic tie-break on candidate id.
    """
    positions: dict[tuple[str, str], int] = {}
    by_run: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_run.setdefault(str(it.get("ranking_run_id")), []).append(it)

    def _sort_key(x: dict[str, Any]) -> tuple[float, str]:
        raw = x.get(score_key)
        score = -1.0 if raw is None else float(raw)
        return (-score, str(x.get("daily_brief_action_candidate_id")))

    for run_items in by_run.values():
        ordered = sorted(run_items, key=_sort_key)
        for idx, it in enumerate(ordered, start=1):
            positions[_item_key(it)] = idx
    return positions


def _rank_outcome_for(
    items: list[dict[str, Any]], positions: dict[tuple[str, str], int]
) -> Optional[float]:
    """rank_outcome_score using the supplied (mode-specific) per-(run,candidate) rank positions."""
    if not items:
        return None
    scored = []
    candidate_count = max(positions.values()) if positions else len(items)
    for it in items:
        scored.append(
            {
                "rank_position": positions.get(_item_key(it), it.get("rank_position") or 1),
                "outcome_type": it.get("outcome_type"),
            }
        )
    return M.rank_outcome_score(scored, candidate_count=candidate_count)


def _outcomes(items: list[dict[str, Any]]) -> list[str]:
    return [it["outcome_type"] for it in items if it.get("outcome_type")]


def _eval_item_row(it: dict[str, Any], rank_position: int) -> dict[str, Any]:
    notes = {
        "deterministic_fallback_used": bool(it.get("deterministic_fallback_used")),
        "is_procore": bool(it.get("is_procore")),
        "actionable": bool(it.get("actionable")),
    }
    return {
        "ranking_run_id": it["ranking_run_id"],
        "daily_brief_action_candidate_id": it["daily_brief_action_candidate_id"],
        "rank_position": rank_position,
        "section_key": it.get("section_key"),
        "candidate_family": normalize_dim(it.get("candidate_family")),
        "source_family": normalize_dim(it.get("source_family")),
        "project_key": normalize_dim(it.get("project_key")),
        "deterministic_score": it.get("deterministic_score"),
        "feedback_score": it.get("feedback_score"),
        "model_advisory_score": it.get("model_advisory_score"),
        "final_score": it.get("final_score"),
        "model_advisory_used": bool(it.get("model_advisory_used")),
        "outcome_type": it.get("outcome_type"),
        "outcome_weight": it.get("outcome_weight"),
        "outcome_lag_hours": it.get("outcome_lag_hours"),
        "source_ref_count": int(it.get("source_ref_count") or 0),
        "eval_notes_json": json.dumps(notes, sort_keys=True),
    }


def evaluate_ranking_policy(
    packet: dict[str, Any], *, eval_mode: str = "observed", policy_version: Optional[str] = None
) -> dict[str, Any]:
    """Evaluate the ranking policy over ``packet`` in ``eval_mode``. Returns a raw-free eval result."""
    if eval_mode not in EVAL_MODES:
        raise ValueError(f"eval_mode must be one of {EVAL_MODES}")

    items = packet.get("items", [])
    runs = packet.get("ranking_runs", [])
    outcomes = _outcomes(items)
    outcome_count = len(outcomes)
    sample_sufficient = outcome_count >= M.MIN_OUTCOME_SAMPLE

    resolved_policy = policy_version or (str(runs[0].get("policy_version")) if runs else None)
    model_profile_id = (
        str(runs[0].get("model_profile_id")) if runs and runs[0].get("model_profile_id") else None
    )
    model_name = str(runs[0].get("model_name")) if runs and runs[0].get("model_name") else None
    feedback_calibration_version = (
        str(runs[0].get("feedback_digest_hash"))
        if runs and runs[0].get("feedback_digest_hash")
        else None
    )

    observed_positions = {_item_key(it): int(it.get("rank_position") or 1) for it in items}
    deterministic_positions = _rerank_positions(items, "deterministic_score")
    model_positions = _rerank_positions(items, "final_score")

    if eval_mode == "deterministic-replay":
        active_positions = deterministic_positions
    elif eval_mode == "model-assisted-observed":
        active_positions = model_positions
    else:  # observed / ablation use the persisted order as the active ranking
        active_positions = observed_positions

    rank_outcome = _rank_outcome_for(items, active_positions)
    deterministic_baseline = _rank_outcome_for(items, deterministic_positions)
    model_assisted = _rank_outcome_for(items, model_positions)

    coverage = M.source_ref_coverage(items)
    degraded_runs = sum(
        1
        for r in runs
        if bool(r.get("deterministic_fallback_used"))
        or str(r.get("model_status") or "") not in ("ok", "model_enriched")
    )
    degradation_rate = M.model_degradation_rate(degraded_runs, len(runs))
    procore = evaluate_procore_noise(packet)
    procore_noise = procore.get("procore_noise_score")

    follow_through = M.accepted_rate(outcomes)  # share of positive disposition (proxy)
    low_noise = 1.0 - (procore_noise if procore_noise is not None else 0.0)
    low_degradation = 1.0 - (degradation_rate if degradation_rate is not None else 0.0)
    usefulness = M.brief_usefulness_score(
        accepted_rate_value=M.accepted_rate(outcomes),
        rank_outcome_score_value=rank_outcome,
        source_ref_coverage_value=coverage,
        low_noise_component=low_noise,
        low_model_degradation_component=low_degradation,
        follow_through_component=follow_through,
    )
    delta = M.deterministic_vs_model_delta(model_assisted, deterministic_baseline)

    eval_items = [
        _eval_item_row(it, active_positions.get(_item_key(it), it.get("rank_position") or 1))
        for it in items
    ]

    return {
        "eval_mode": eval_mode,
        "window_start": packet["window_start"],
        "window_end": packet["window_end"],
        "ignored_lag_hours": packet.get("ignored_lag_hours", M.DEFAULT_IGNORED_LAG_HOURS),
        "policy_version": resolved_policy,
        "ranking_algorithm_version": RANKING_ALGORITHM_VERSION,
        "assembly_policy_version": ASSEMBLY_POLICY_VERSION,
        "model_profile_id": model_profile_id,
        "model_name": model_name,
        "feedback_calibration_version": feedback_calibration_version,
        "candidate_count": len(items),
        "outcome_count": outcome_count,
        "sample_sufficient": sample_sufficient,
        "metrics": {
            "accepted_rate": M.accepted_rate(outcomes),
            "rejected_rate": M.rejected_rate(outcomes),
            "snoozed_rate": M.snoozed_rate(outcomes),
            "ignored_rate": M.ignored_rate(outcomes),
            "rank_outcome_score": rank_outcome,
            "deterministic_baseline_rank_outcome": deterministic_baseline,
            "model_assisted_rank_outcome": model_assisted,
            "deterministic_vs_model_delta": delta,
            "source_ref_coverage": coverage,
            "brief_usefulness_score": usefulness,
            "model_degradation_rate": degradation_rate,
            "procore_noise_score": procore_noise,
        },
        "eval_items": eval_items,
        "advisory": True,
        "observational_only": True,
        "confidence_note": (
            "insufficient_sample until enough reviewed outcomes exist"
            if not sample_sufficient
            else "observational_only_not_causal"
        ),
    }
