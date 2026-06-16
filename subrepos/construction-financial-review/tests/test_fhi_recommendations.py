"""Advisory adjustment: floored at actuals, never capped, do-not-auto-apply, history never an actual."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_recommendations as hrec

CFG = {"history_max_weight_when_validated": "0.45", "history_max_weight_when_unvalidated": "0.20"}


def _sig(remaining_latest):
    return {"budget_code_key": "1000.20-18-110.OVH", "cost_code": "20-18-110",
            "historical_remaining_forecast_latest": remaining_latest,
            "historical_pattern_class": "decreasing_tapering_exposure",
            "latest_curve_shape_class": "tapering_closeout"}


def _rec(actual="100000.00", recommended="500000.00", worst="700000.00",
         projected="480000.00", revised="450000.00"):
    return {"actual_cost_all_source_to_date": actual, "recommended_final_cost": recommended,
            "worst_credible_final_cost": worst, "current_projected_cost": projected,
            "revised_budget": revised}


def test_adjustment_is_advisory_and_uncapped():
    sig = _sig("300000.00")
    v = {"validation_class": "validated_aligned", "burn_acceleration_class": "steady"}
    rel = {"overall_history_reliability_score": "0.7000"}
    a = hrec.build_adjustment(sig, v, rel, _rec(), {}, CFG, "tropical")
    assert a["do_not_auto_apply"] is True
    assert a["upper_cap_applied"] is False
    assert a["requires_human_acceptance"] is True


def test_adjusted_floored_at_actuals():
    # history implies a very low final; the advisory adjusted cost cannot drop below actual cost to date
    sig = _sig("0.00")
    v = {"validation_class": "validated_zero_inactive", "burn_acceleration_class": "steady"}
    rel = {"overall_history_reliability_score": "1.0000"}
    a = hrec.build_adjustment(sig, v, rel, _rec(actual="120000.00", recommended="120050.00"),
                              {}, CFG, "tropical")
    assert Decimal(a["history_informed_adjusted_final_cost"]) >= Decimal("120000.00")


def test_low_reliability_defers_to_actuals():
    sig = _sig("300000.00")
    v = {"validation_class": "contradicted_escalation", "burn_acceleration_class": "accelerating"}
    rel = {"overall_history_reliability_score": "0.0500"}
    a = hrec.build_adjustment(sig, v, rel, _rec(), {}, CFG, "tropical")
    assert a["history_informed_direction"] == "defer_to_actuals_review"
    # near-zero pull toward history when unreliable
    assert abs(Decimal(a["history_informed_adjustment_amount"])) < Decimal("20000")
