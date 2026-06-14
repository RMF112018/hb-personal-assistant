"""Schedule integration action rules: exhaustion threshold, blocked decreases, preserved increases."""
from construction_financial_review.schedule_analysis import forecast_integration as fi
from construction_financial_review.schedule_analysis import schedule_rollup as sr


def _rollup(status=sr.RW_MATERIAL, neg_float=0, mapping="mapped", open_count=4):
    return {
        "budget_code_key": "1000.15-02-010.SUB",
        "schedule_mapping_status": mapping,
        "schedule_mapping_confidence": "high",
        "schedule_remaining_work_status": status,
        "open_activity_count": open_count,
        "remaining_duration_days": "30.00",
        "negative_float_activity_count": neg_float,
        "schedule_risk_flags": [],
        "minimum_total_float_days": -5.0 if neg_float else 1.0,
        "cashflow_timing_usable": True,
        "mapped_activity_count": open_count,
        "ambiguous_candidate_activity_count": 0,
    }


def _rec(action, projected="100.00", actual="10.00", rec_proj="100.00", rec_adj="0.00"):
    return {
        "budget_code_key": "1000.15-02-010.SUB",
        "forecast_action": action,
        "current_projected_cost": projected,
        "actual_cost_all_source_to_date": actual,
        "recommended_projected_cost": rec_proj,
        "recommended_forecast_adjustment": rec_adj,
        "confidence": "high",
    }


def test_actuals_near_projected_threshold():
    assert fi.actuals_near_projected("90.00", "100.00") is True     # exactly 90%
    assert fi.actuals_near_projected("89.99", "100.00") is False
    assert fi.actuals_near_projected("100.00", "0.00") is False     # no projected


def test_decrease_blocked_by_material_remaining_work():
    out = fi.integrate_recommendation(_rec("decrease_forecast", rec_proj="80.00", rec_adj="-20.00"),
                                      _rollup(status=sr.RW_MATERIAL))
    assert out["schedule_integrated_forecast_action"] == "review_required"
    assert out["schedule_integrated_recommended_projected_cost"] is None
    assert out["schedule_integrated_recommended_forecast_adjustment"] is None
    assert "schedule_blocks_decrease" in out["schedule_risk_flags"]
    assert out["action_changed_by_schedule"] is True


def test_decrease_preserved_when_no_material_remaining():
    out = fi.integrate_recommendation(_rec("decrease_forecast", rec_proj="80.00"),
                                      _rollup(status=sr.RW_MINOR))
    assert out["schedule_integrated_forecast_action"] == "decrease_forecast"
    assert out["schedule_integrated_recommended_projected_cost"] == "80.00"


def test_increase_preserved_with_remaining_exposure_flag():
    out = fi.integrate_recommendation(
        _rec("increase_forecast", projected="100.00", actual="120.00", rec_proj="120.00", rec_adj="20.00"),
        _rollup(status=sr.RW_MATERIAL))
    assert out["schedule_integrated_forecast_action"] == "increase_forecast"
    assert out["schedule_integrated_recommended_projected_cost"] == "120.00"   # number unchanged
    assert "remaining_exposure_review_required" in out["schedule_risk_flags"]


def test_hold_with_exhaustion_becomes_review():
    out = fi.integrate_recommendation(_rec("hold_current_forecast", projected="100.00", actual="95.00"),
                                      _rollup(status=sr.RW_MATERIAL))
    assert out["schedule_integrated_forecast_action"] == "review_required"
    assert "schedule_open_work_with_forecast_exhaustion" in out["schedule_risk_flags"]
    assert out["confidence_after_schedule"] == "medium"   # notched down from high


def test_hold_without_exhaustion_stays_hold():
    out = fi.integrate_recommendation(_rec("hold_current_forecast", projected="100.00", actual="10.00"),
                                      _rollup(status=sr.RW_MATERIAL))
    assert out["schedule_integrated_forecast_action"] == "hold_current_forecast"
    assert out["schedule_integrated_recommended_projected_cost"] == "100.00"


def test_schedule_never_creates_numeric_increase():
    """The integrated projected cost must never exceed the baseline recommended projected cost."""
    for action in ("hold_current_forecast", "review_required", "insufficient_evidence"):
        out = fi.integrate_recommendation(_rec(action, projected="100.00", rec_proj="100.00"),
                                          _rollup(status=sr.RW_MATERIAL))
        si = out["schedule_integrated_recommended_projected_cost"]
        assert si in (None, "100.00")   # never raised above baseline


def test_ambiguous_mapping_flagged_and_no_promotion():
    out = fi.integrate_recommendation(_rec("insufficient_evidence", rec_proj=None),
                                      _rollup(status=sr.RW_AMBIGUOUS, mapping="ambiguous"))
    assert out["schedule_integrated_forecast_action"] == "insufficient_evidence"
    assert "schedule_mapping_ambiguous" in out["schedule_risk_flags"]
