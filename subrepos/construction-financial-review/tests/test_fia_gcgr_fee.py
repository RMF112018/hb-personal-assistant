"""Priority 6 fee projected-budget cap + GC/GR behavior tests."""
from construction_financial_review.forecast_improvement_audit import gcgr_fee

from tests._fia_fixtures import FEE_KEY, NONFEE_KEY, budget_entry, minimal_inputs


def _inputs_with_fee(projected_budget, recommended, actual, cost_code="20-18-110"):
    fee = budget_entry(FEE_KEY, cost_code, "CONTRACTOR'S FEE.Overhead",
                       projected_budget=projected_budget, projected_costs="0",
                       revised_budget="2281157.26", costentries_total_amount=actual,
                       forecast_to_complete="0")
    return minimal_inputs(
        budget_by_key={FEE_KEY: fee},
        accuracy_by_key={FEE_KEY: {
            "budget_code_key": FEE_KEY, "recommended_final_cost": recommended,
            "actual_cost_all_source_to_date": actual, "worst_credible_final_cost": recommended}})


def test_case1_evidence_exceeds_cap_is_capped():
    rows, gaps = gcgr_fee.build_fee_cap(_inputs_with_fee("100000", "150000", "0"), {})
    r = rows[0]
    assert r["fee_cap_basis"] == "projected_budget_value"
    assert r["fee_projected_budget_cap_applied"] is True
    assert r["fee_forecast_after_cap"] == r["fee_projected_budget_cap_value"] == "100000.00"
    assert r["evidence_supported_fee_before_cap"] == "150000.00"


def test_case2_projected_budget_below_evidence_sets_applied_true():
    rows, _ = gcgr_fee.build_fee_cap(_inputs_with_fee("250000", "300000", "10000"), {})
    r = rows[0]
    assert r["fee_projected_budget_cap_applied"] is True
    assert r["fee_forecast_after_cap"] == "250000.00"
    assert r["actuals_exceed_fee_cap_exception"] is False


def test_case3_actuals_exceed_cap_floor_preserved_exception():
    rows, _ = gcgr_fee.build_fee_cap(_inputs_with_fee("100000", "150000", "200000"), {})
    r = rows[0]
    assert r["actuals_exceed_fee_cap_exception"] is True
    assert r["fee_forecast_after_cap"] == "200000.00"          # actuals floor wins, never below actuals
    assert r["fee_projected_budget_cap_applied"] is False       # cap superseded by actuals


def test_case4_missing_cap_value_data_gap_no_invented_cap():
    rows, gaps = gcgr_fee.build_fee_cap(_inputs_with_fee(None, "150000", "0"), {})
    r = rows[0]
    assert r["fee_cap_basis"] == "none"
    assert r["fee_projected_budget_cap_value"] is None
    assert r["fee_projected_budget_cap_applied"] is False
    assert any(g["gap_type"] == "fee_cap_value_missing" for g in gaps)


def test_case4b_zero_cap_value_is_treated_as_missing():
    rows, gaps = gcgr_fee.build_fee_cap(_inputs_with_fee("0", "150000", "0"), {})
    assert rows[0]["fee_cap_basis"] == "none"
    assert any(g["gap_type"] == "fee_cap_value_missing" for g in gaps)


def test_case5_non_fee_code_not_in_fee_rows():
    nonfee = budget_entry(NONFEE_KEY, "15-03-100", "DRYWALL.Subcontract",
                          projected_budget="50000", projected_costs="60000",
                          revised_budget="55000", costentries_total_amount="40000")
    rows, _ = gcgr_fee.build_fee_cap(minimal_inputs(budget_by_key={NONFEE_KEY: nonfee}), {})
    assert rows == []


def test_evidence_below_cap_not_binding():
    rows, _ = gcgr_fee.build_fee_cap(_inputs_with_fee("2294000.41", "0", "0"), {})
    r = rows[0]
    assert r["fee_projected_budget_cap_applied"] is False       # evidence below cap -> not binding
    assert r["fee_forecast_after_cap"] == "0.00"
    assert r["fee_cap_basis"] == "projected_budget_value"


def test_fee_followups_flag_required_implementation():
    inp = _inputs_with_fee("100000", "150000", "0")
    rows, _ = gcgr_fee.build_fee_cap(inp, {})
    gaps = gcgr_fee.fee_followups(inp, {}, rows)
    g = gaps[0]
    assert g["gap_type"] == "required_follow_up_implementation"
    assert g["upstream_fee_forecast_currently_exceeds_cap"] is True
    assert g["do_not_auto_apply"] is True


def test_gcgr_behavior_advisory_and_class():
    fee = budget_entry(FEE_KEY, "20-18-110", "CONTRACTOR'S FEE.Overhead",
                       costentries_total_amount="0", forecast_to_complete="0",
                       projected_budget="100000")
    rows = gcgr_fee.build_gcgr_behavior(minimal_inputs(
        budget_codes=[fee], budget_by_key={FEE_KEY: fee}), {})
    assert rows and rows[0]["gcgr_behavior_class"] == "stable_zero_inactive"
    assert rows[0]["requires_human_acceptance"] is True
    assert rows[0]["note"].startswith("advisory")
