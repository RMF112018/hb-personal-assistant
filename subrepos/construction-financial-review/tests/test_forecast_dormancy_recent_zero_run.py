"""forecast_dormancy: recent-zero-run suppression for staffing / general-conditions codes."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_dormancy.classify import classify

CFG = {
    "lookback_months_without_actual_cost": 18,
    "closed_description_patterns": ["CLOSED - DO NOT USE", "DO NOT USE", "INACTIVE"],
    "closed_bare_token_status_fields": ["sub_job_description"],
    "recent_zero_run": {
        "enabled": True,
        "staffing_gc": {"enabled": True, "trailing_zero_month_threshold": 3},
        "non_staffing": {"enabled": False, "trailing_zero_month_threshold": 6},
        "staffing_general_conditions_cost_code_families": ["10-01"],
        "staffing_general_conditions_categories": ["LAB", "LBN"],
        "staffing_description_terms": ["SUPERINTENDENT", "PROJECT MANAGER", "LABOR BURDEN",
                                       "GENERAL CONDITIONS", "STAFF", "SALARY", "PAYROLL"],
        "use_staffing_plan_code_list": True,
    },
}
SLIST = ["1000.10-01-312.LAB", "1000.10-01-312.LBN"]


def _inp(**kw):
    d = dict(budget_code_key="1000.10-01-312.LAB", cost_code="10-01-312", category="LAB",
             sub_job_description="TROPICAL WORLD NURSERY-CONSTR",
             budget_code_description="TROPICAL WORLD NURSERY-CONSTR.SUPERINTENDENT 1.Labor",
             cost_type_description="Labor", current_forecast_month="2026-06",
             monthly_actuals=[{"month": "2025-12", "amount_decimal_string": "4000.00"},
                              {"month": "2026-03", "amount_decimal_string": "3923.52"}],  # 3-month run to 06
             actual_cost_to_date="163778.24", revised_budget="199336.71", projected_costs="163778.24",
             committed_costs="0.00", commitment_invoiced="0.00", owner_latest_period_to=None,
             procore_latest_period_end=None, schedule_remaining_work_status="no_schedule_evidence",
             schedule_open_activity_count=0, schedule_latest_finish=None, model_control=None,
             staffing_code_list=SLIST, staffing_plan_future_assignment=False)
    d.update(kw)
    return d


def test_staffing_code_recent_zero_run_suppresses():
    d = classify(_inp(), CFG)
    assert d["dormant_status"] == "recent_zero_run_after_prior_activity" and d["suppression_applied"] is True
    assert d["months_since_last_actual"] == 3 and d["staffing_or_general_conditions_code"] is True
    assert d["prior_activity_detected"] is True and d["recent_zero_run_detected"] is True
    assert d["zero_run_threshold_used"] == 3


def test_staffing_plan_assignment_prevents_suppression():
    d = classify(_inp(staffing_plan_future_assignment=True), CFG)
    assert d["dormant_status"] == "active_with_remaining_evidence" and d["suppression_applied"] is False
    assert "staffing_plan_future_assignment" in d["remaining_evidence"]


def test_shape_only_control_does_not_revive_stopped_staffing():
    d = classify(_inp(model_control={"control_id": "s", "changes_deterministic_final": False,
                                     "controlled_remaining": Decimal("0")}), CFG)
    assert d["dormant_status"] == "recent_zero_run_after_prior_activity" and d["suppression_applied"] is True


def test_value_asserting_manual_control_revives_with_disclosure():
    d = classify(_inp(model_control={"control_id": "m", "changes_deterministic_final": True,
                                     "controlled_remaining": Decimal("5000.00")}), CFG)
    assert d["dormant_status"] == "operator_controlled" and d["suppression_applied"] is False
    assert d["operator_control_override"] is True


def test_mat_with_family_and_description_suppresses():
    d = classify(_inp(budget_code_key="1000.10-01-312.MAT", category="MAT",
                      budget_code_description="TROPICAL WORLD NURSERY-CONSTR.SUPERINTENDENT 1.Materials",
                      cost_type_description="Materials"), CFG)
    assert d["staffing_or_general_conditions_code"] is True
    assert d["dormant_status"] == "recent_zero_run_after_prior_activity" and d["suppression_applied"] is True


def test_gc_material_without_staffing_term_not_suppressed():
    # family 10-01 alone is NOT enough for a MAT code
    d = classify(_inp(budget_code_key="1000.10-01-099.MAT", category="MAT",
                      budget_code_description="TROPICAL WORLD NURSERY-CONSTR.TEMPORARY FENCING.Materials",
                      cost_type_description="Materials"), CFG)
    assert d["staffing_or_general_conditions_code"] is False
    assert d["suppression_applied"] is False and d["dormant_status"] == "active_forecastable"


def test_non_staffing_recent_zero_run_is_advisory_only():
    # non-staffing SUB idle 7 months: arm disabled => not suppressed, advisory flags set
    d = classify(_inp(budget_code_key="1000.15-07-590.SUB", cost_code="15-07-590", category="SUB",
                      sub_job_description="X", budget_code_description="X.ROOFING.Sub",
                      cost_type_description="Sub", staffing_code_list=[],
                      monthly_actuals=[{"month": "2025-11", "amount_decimal_string": "1000.00"}]), CFG)
    assert d["suppression_applied"] is False and d["dormant_status"] == "active_forecastable"
    assert d["recent_zero_run_detected"] is True and d["non_staffing_suppression_candidate"] is True
    assert d["suppression_reason"] == "non_staffing_recent_zero_run_advisory_only"


def test_staffing_paid_within_threshold_stays_active():
    d = classify(_inp(monthly_actuals=[{"month": "2026-04", "amount_decimal_string": "500.00"}]), CFG)  # 2mo
    assert d["dormant_status"] == "active_forecastable" and d["suppression_applied"] is False


def test_recent_cost_overrides_closure_non_staffing():
    d = classify(_inp(budget_code_key="0000.03-01-099.SUB", cost_code="03-01-099", category="SUB",
                      sub_job_description="CLOSED - DO NOT USE",
                      budget_code_description="CLOSED - DO NOT USE.X.Sub", cost_type_description="Sub",
                      staffing_code_list=[],
                      monthly_actuals=[{"month": "2026-04", "amount_decimal_string": "500.00"}]), CFG)
    assert d["dormant_status"] == "active_forecastable" and d["suppression_applied"] is False


# ---- live intelligence e2e: the three SUPERINTENDENT codes ----

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
TROP = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(TROP["default_data_root"])
EXAMPLES = ["1000.10-01-312.LAB", "1000.10-01-312.LBN", "1000.10-01-312.MAT"]


@pytest.mark.skipif(
    not (DATA_ROOT.is_dir() and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_analysis_package_tropical_crosswalk_v2_*"))),
    reason="local forecast data root / required packages not present")
def test_live_superintendent_codes_recent_zero_run_suppressed(tmp_path):
    from construction_financial_review.forecast_intelligence import generate_forecast_intelligence_package as igen
    res = igen.generate("tropical", TROP, data_root=DATA_ROOT, frozen_stamp="20260106_000000", out_root=tmp_path)
    assert res["validation_passed"] is True
    pkg = Path(res["output_package"])
    recs = {r["budget_code_key"]: r for r in read_jsonl(pkg / "forecast_recommendations_by_budget_code.jsonl")}
    status = {r["budget_code_key"]: r for r in read_jsonl(pkg / "dormant_code_status_by_budget_code.jsonl")}
    for k in EXAMPLES:
        r, s = recs[k], status[k]
        assert s["dormant_status"] == "recent_zero_run_after_prior_activity", k
        assert s["suppression_applied"] is True and s["staffing_or_general_conditions_code"] is True, k
        assert r["recommended_cost_to_complete"] == "0.00", k
        assert r["recommended_final_cost"] == r["actual_cost_all_source_to_date"], k
    vr = read_json(pkg / "validation_report.json")
    assert vr["checks"]["no_positive_forecast_for_recent_zero_run_without_evidence"] is True
