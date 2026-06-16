"""forecast_dormancy: deterministic classifier + suppression unit tests (no data root)."""
from __future__ import annotations

from decimal import Decimal

from construction_financial_review.forecast_dormancy import suppress
from construction_financial_review.forecast_dormancy.classify import classify

CFG = {"lookback_months_without_actual_cost": 18,
       "closed_description_patterns": ["CLOSED - DO NOT USE", "DO NOT USE", "INACTIVE"],
       "closed_bare_token_status_fields": ["sub_job_description"]}


def _inp(**kw):
    d = dict(budget_code_key="0000.03-01-413.MAT", cost_code="03-01-413", category="MAT",
             sub_job_description="CLOSED - DO NOT USE",
             budget_code_description="CLOSED - DO NOT USE.ESTIMATING.Materials",
             cost_type_description="Materials", current_forecast_month="2026-06",
             monthly_actuals=[{"month": "2024-12", "amount_decimal_string": "500.00"}],
             actual_cost_to_date="4278.99", revised_budget="4278.99", projected_costs="4278.99",
             committed_costs="0.00", commitment_invoiced="0.00", owner_latest_period_to=None,
             procore_latest_period_end=None, schedule_remaining_work_status="no_schedule_evidence",
             schedule_open_activity_count=0, schedule_latest_finish=None, model_control=None)
    d.update(kw)
    return d


def test_closed_no_recent_cost_suppresses():
    d = classify(_inp(), CFG)
    assert d["dormant_status"] == "closed_do_not_use" and d["suppression_applied"] is True
    assert d["months_since_last_actual"] == 18 and d["closure_phrase_detected"] is True
    assert "CLOSED - DO NOT USE" in d["suppression_reason"] and "idle" in d["suppression_reason"]


def test_eighteen_months_idle_no_evidence_suppresses():
    d = classify(_inp(sub_job_description="ESTIMATING",
                      budget_code_description="ESTIMATING.Materials",
                      monthly_actuals=[{"month": "2024-12", "amount_decimal_string": "5.00"}]), CFG)
    assert d["dormant_status"] == "dormant_no_recent_cost" and d["suppression_applied"] is True


def test_recent_cost_overrides_closure():
    d = classify(_inp(monthly_actuals=[{"month": "2026-03", "amount_decimal_string": "100.00"}]), CFG)
    assert d["dormant_status"] == "active_forecastable" and d["suppression_applied"] is False


def test_open_commitment_overrides_dormancy():
    d = classify(_inp(committed_costs="10000.00", commitment_invoiced="2000.00"), CFG)
    assert d["dormant_status"] == "active_with_remaining_evidence" and d["suppression_applied"] is False
    assert any("open_commitment_remaining" in e for e in d["remaining_evidence"])


def test_value_asserting_operator_control_revives():
    d = classify(_inp(model_control={"control_id": "x", "changes_deterministic_final": True,
                                     "controlled_remaining": Decimal("5000.00")}), CFG)
    assert d["dormant_status"] == "operator_controlled" and d["suppression_applied"] is False
    assert d["operator_control_override"] is True


def test_shape_only_control_does_not_revive():
    # shape/window/timing-only control => changes_deterministic_final False => dormancy still applies
    d = classify(_inp(model_control={"control_id": "s", "changes_deterministic_final": False,
                                     "controlled_remaining": Decimal("0")}), CFG)
    assert d["dormant_status"] == "closed_do_not_use" and d["suppression_applied"] is True


def test_value_control_with_zero_remaining_does_not_revive():
    d = classify(_inp(model_control={"control_id": "z", "changes_deterministic_final": True,
                                     "controlled_remaining": Decimal("0")}), CFG)
    assert d["dormant_status"] == "closed_do_not_use" and d["suppression_applied"] is True


def test_never_had_cost_inactive():
    d = classify(_inp(sub_job_description="ESTIMATING", budget_code_description="ESTIMATING.Materials",
                      monthly_actuals=[], actual_cost_to_date="0.00"), CFG)
    assert d["dormant_status"] == "inactive_no_remaining_evidence" and d["suppression_applied"] is True


def test_stale_history_no_recent_suppresses():
    d = classify(_inp(sub_job_description="ESTIMATING", budget_code_description="ESTIMATING.Materials",
                      monthly_actuals=[{"month": "2023-01", "amount_decimal_string": "9000.00"},
                                       {"month": "2023-02", "amount_decimal_string": "8000.00"}]), CFG)
    assert d["dormant_status"] == "dormant_no_recent_cost" and d["suppression_applied"] is True


def test_bare_closed_only_in_status_field_not_free_text():
    # "closed cell insulation" in a description must NOT trigger closure
    d = classify(_inp(sub_job_description="INSULATION",
                      budget_code_description="INSULATION.CLOSED CELL SPRAY FOAM.Materials",
                      monthly_actuals=[{"month": "2024-12", "amount_decimal_string": "500.00"}]), CFG)
    assert d["closure_phrase_detected"] is False
    # idle 18mo with no evidence still dormant (by inactivity, not closure)
    assert d["dormant_status"] == "dormant_no_recent_cost"


def test_suppress_recommendation_zeroes_and_anchors():
    rec = {"actual_cost_all_source_to_date": "4278.99", "recommended_cost_to_complete": "10767.05",
           "recommended_final_cost": "15046.04", "worst_credible_final_cost": "16000.00",
           "overrun_projected": True}
    new, before = suppress.suppress_recommendation(rec, classify(_inp(), CFG))
    assert new["recommended_cost_to_complete"] == "0.00"
    assert new["recommended_final_cost"] == "4278.99" and new["worst_credible_final_cost"] == "4278.99"
    assert new["overrun_projected"] is False
    assert new["dormant_forecast_basis"] == "closed_do_not_use_zero_remaining"
    assert before["recommended_cost_to_complete"] == "10767.05"


def test_audit_row_shape():
    d = classify(_inp(), CFG)
    row = suppress.audit_row(d, {"recommended_cost_to_complete": "10767.05",
                                 "recommended_final_cost": "15046.04"})
    assert row["recommended_cost_to_complete_after_suppression"] == "0.00"
    assert row["final_forecast_after_suppression"] == "4278.99"
    assert row["closure_phrase_detected"] is True
    for f in ("dormant_status", "months_since_last_actual", "suppression_reason", "operator_control_override"):
        assert f in row
