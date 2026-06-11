"""Phase 10 V52 — effectiveness metric engine tests (fixed-value, deterministic)."""

from __future__ import annotations

from hb_assistant.construction.second_brain.local_ai import daily_brief_effectiveness_metrics as M


def test_outcome_rates_are_deterministic() -> None:
    outcomes = ["accepted", "rejected", "rejected", "snoozed", "ignored"]
    assert M.accepted_rate(outcomes) == 0.2
    assert M.rejected_rate(outcomes) == 0.4
    assert M.snoozed_rate(outcomes) == 0.2
    assert M.ignored_rate(outcomes) == 0.2
    assert M.accepted_rate([]) == 0.0  # no eligible denominator


def test_absent_feedback_is_not_acceptance() -> None:
    # Pending (no outcome) items are simply not present in the outcome list — never counted accepted.
    assert M.accepted_rate(["ignored", "ignored"]) == 0.0


def test_rank_outcome_score_fixed_example() -> None:
    items = [
        {"rank_position": 1, "outcome_type": "accepted"},  # weight 1.0, rank_weight 1.0
        {"rank_position": 3, "outcome_type": "rejected"},  # weight -0.8, rank_weight 0.0
    ]
    # raw mean = (1.0*1.0 + (-0.8)*0.0)/2 = 0.5 ; mapped (0.5+1)/2 = 0.75
    assert M.rank_outcome_score(items, candidate_count=3) == 0.75
    assert M.rank_outcome_score([{"rank_position": 1, "outcome_type": None}]) is None


def test_brief_usefulness_score_weighted_blend() -> None:
    score = M.brief_usefulness_score(
        accepted_rate_value=1.0,
        rank_outcome_score_value=1.0,
        source_ref_coverage_value=1.0,
        low_noise_component=1.0,
        low_model_degradation_component=1.0,
        follow_through_component=1.0,
    )
    assert score == 1.0
    zero = M.brief_usefulness_score(
        accepted_rate_value=0.0,
        rank_outcome_score_value=None,
        source_ref_coverage_value=0.0,
        low_noise_component=0.0,
        low_model_degradation_component=0.0,
        follow_through_component=0.0,
    )
    assert zero == 0.0


def test_procore_noise_score_stable() -> None:
    # (rejected 2 + ignored 1 + suppressed 0)/exposed 4 = 0.75 ; rank penalty (1/4)*0.25 = 0.0625
    assert (
        M.procore_noise_score(
            exposed_procore=4, rejected=2, ignored=1, suppressed=0, top_rank_noisy=1
        )
        == 0.8125
    )
    assert M.procore_noise_score(exposed_procore=0, rejected=0, ignored=0, suppressed=0) is None


def test_model_degradation_rate() -> None:
    assert M.model_degradation_rate(1, 2) == 0.5
    assert M.model_degradation_rate(0, 0) is None


def test_duplicate_precision_proxy_marks_small_sample() -> None:
    small = M.duplicate_precision_proxy(merged_as_duplicate=1, reviewed_clusters=2)
    assert small["insufficient_sample"] is True
    assert small["value"] == 0.5
    big = M.duplicate_precision_proxy(merged_as_duplicate=3, reviewed_clusters=6)
    assert big["insufficient_sample"] is False
    assert big["value"] == 0.5


def test_source_ref_coverage_over_actionable_only() -> None:
    items = [
        {"actionable": True, "source_ref_count": 1},
        {"actionable": True, "source_ref_count": 0},
        {"actionable": False, "source_ref_count": 0},  # non-actionable excluded
    ]
    assert M.source_ref_coverage(items) == 0.5
    assert M.source_ref_coverage([{"actionable": False, "source_ref_count": 0}]) == 1.0


def test_feedback_calibration_lift_insufficient_when_small() -> None:
    r = M.feedback_calibration_lift(
        calibrated_policy_score=0.7, baseline_policy_score=0.5, sample_size=3
    )
    assert r["insufficient_sample"] is True
    r2 = M.feedback_calibration_lift(
        calibrated_policy_score=0.7, baseline_policy_score=0.5, sample_size=10
    )
    assert r2["insufficient_sample"] is False
    assert r2["value"] == 0.2
    r3 = M.feedback_calibration_lift(
        calibrated_policy_score=None, baseline_policy_score=0.5, sample_size=10
    )
    assert r3["value"] is None


def test_deterministic_vs_model_delta_is_non_causal() -> None:
    r = M.deterministic_vs_model_delta(0.6, 0.5)
    assert r["value"] == 0.1
    assert r["causal"] is False
    assert M.deterministic_vs_model_delta(None, 0.5)["value"] is None
