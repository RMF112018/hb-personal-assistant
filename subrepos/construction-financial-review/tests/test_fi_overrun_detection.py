"""Overrun detection: defined vs current projected cost, never suppressed for exceeding ERP/budget."""
from decimal import Decimal

from construction_financial_review.common.money import D
from construction_financial_review.forecast_intelligence import (estimators_uncapped as est,
                                                                 reconcile_final as rf)


def _bundle(**over):
    b = {
        "project_key": "tropical",
        "actual_cost_all_source_to_date": "100000.00",
        "projected_costs": "120000.00",
        "revised_budget": "110000.00",
        "committed_costs": "0.00",
        "owner_sov_value": None,
        "owner_mapping_status": "none",
        "procore_mapping_status": "none",
        "avg_monthly_burn": "0.00",
        "schedule_influences_estimate": False,
        "schedule_confidence": "0.0",
        "schedule_remaining_work_status": "no_schedule_evidence",
        "trend_signal": "hold",
        "cost_volatility_cov": None,
        "months_of_completed_actuals": 6,
        "data_gap_flags": [],
    }
    b.update(over)
    return b


def _select(b):
    ests = est.estimate_all(b)
    return rf.select_final("1000.15-16-110.SUB", "tropical", ests, b, {})


def test_overrun_projected_is_vs_current_projected_cost():
    b = _bundle(owner_mapping_status="mapped", owner_latest_percent_complete="0.5")  # EAC 200k
    r = _select(b)
    assert r["forecast_direction"] == "increase"
    assert r["overrun_projected"] is True
    assert r["overrun_vs_current_projected_cost"] is True
    # overrun_projected mirrors the current-projected flag, NOT the budget flag
    assert r["overrun_projected"] == r["overrun_vs_current_projected_cost"]


def test_separate_reference_flags_independent():
    b = _bundle(owner_mapping_status="mapped", owner_latest_percent_complete="0.5",
                committed_costs="50000.00", owner_sov_value="90000.00")  # EAC ~200k
    r = _select(b)
    assert r["overrun_vs_current_projected_cost"] is True     # 200k > 120k
    assert r["overrun_vs_revised_budget"] is True             # 200k > 110k
    assert r["overrun_vs_committed_cost"] is True             # 200k > 50k
    assert r["overrun_vs_owner_scope_value"] is True          # 200k > 90k


def test_overrun_not_suppressed_when_exceeds_erp():
    # Commitment far above ERP; the overrun must be reported (recommended > projected), and the
    # worst-credible ceiling captures the full contractual exposure.
    b = _bundle(committed_costs="900000.00")
    r = _select(b)
    assert r["overrun_projected"] is True
    assert D(r["recommended_final_cost"]) > D(b["projected_costs"])
    assert D(r["worst_credible_final_cost"]) >= Decimal("900000.00")


def test_decrease_only_when_defensible():
    # Model below projected but NOT near-complete + no schedule-complete -> downgraded to hold.
    b = _bundle(projected_costs="500000.00", owner_mapping_status="mapped",
                owner_latest_percent_complete="0.40")  # EAC = 100000/0.4 = 250k < 500k
    r = _select(b)
    assert D(r["recommended_final_cost"]) < D(b["projected_costs"])
    assert r["forecast_direction"] == "hold"   # not 'decrease' (not near-complete)


def test_decrease_allowed_when_near_complete_stable():
    b = _bundle(projected_costs="500000.00", owner_mapping_status="mapped",
                owner_latest_percent_complete="0.99", schedule_remaining_work_status="complete",
                cost_volatility_cov="0.10", trend_signal="hold")
    r = _select(b)
    assert r["forecast_direction"] == "decrease"


def test_insufficient_evidence_never_uses_erp_as_floor():
    # No independent evidence at all -> recommended = actual, NOT ERP projected.
    # (projected present only as a reference; it must not become the modeled answer.)
    b = _bundle(projected_costs=None)
    r = _select(b)
    assert r["n_independent_models"] == 0
    assert r["forecast_direction"] == "insufficient_evidence"
    assert D(r["recommended_final_cost"]) == D(b["actual_cost_all_source_to_date"])
    assert "no_independent_model_evidence" in r["limiting_data_gaps"]


def test_dual_posture_worst_credible_geq_recommended():
    b = _bundle(owner_mapping_status="mapped", owner_latest_percent_complete="0.5",
                committed_costs="250000.00")
    r = _select(b)
    assert D(r["worst_credible_final_cost"]) >= D(r["recommended_final_cost"])
