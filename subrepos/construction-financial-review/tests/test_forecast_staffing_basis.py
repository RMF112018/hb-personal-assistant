"""Unit tests for the operator staffing-plan cost-basis module (forecast_staffing_basis)."""
from decimal import Decimal as D

from construction_financial_review.forecast_staffing_basis import (
    classify_staffing_basis,
    validate_staffing_basis_decisions,
)
from construction_financial_review.forecast_staffing_basis.apply import (
    apply_staffing_basis_decision,
    build_staffing_basis_audit_row,
)

ACCEPTED = "mapped_operator_approved_lab"


def _base(**over):
    inp = dict(budget_code_key="1000.10-01-318.LAB", cost_code="10-01-318", category="LAB",
               actual_cost_to_date="299380.32", current_model_final="322525.97",
               current_model_ctc="23145.65", staffing_plan_implied_remaining_cost="109045.44",
               staffing_plan_implied_final_cost="408425.76", staffing_mapping_status=ACCEPTED,
               staffing_applied_numeric=True, staffing_source_validation_passed=True,
               operator_acceptance_status="pending")
    inp.update(over)
    return inp


def _apply(inp):
    return apply_staffing_basis_decision(
        D(inp["current_model_final"]), D(inp["current_model_ctc"]), D(inp["actual_cost_to_date"]), inp)


# mapped accepted .LAB raise applies the staffing basis (the canonical regression)
def test_mapped_accepted_lab_raise_applies():
    nf, nc, d = _apply(_base())
    assert d["staffing_basis_status"] == "operator_staffing_plan_basis"
    assert nc == D("109045.44") and nf == D("408425.76")
    assert "raise_only" in d["reason"][0]


# monthly total reconciles to the staffing CTC (audit row)
def test_monthly_reconciles_to_staffing_ctc():
    d = classify_staffing_basis(_base())
    row = build_staffing_basis_audit_row(d, monthly_total_after_staffing_basis=D("109045.44"))
    assert D(row["monthly_total_after_staffing_basis"]) == D("109045.44")
    assert D(row["final_reconciliation_variance"]) == D("0.00")


# actuals floor preserved (implied final always >= actual for a raise)
def test_actuals_floor_respected():
    nf, nc, d = _apply(_base())
    assert nf >= D(_base()["actual_cost_to_date"])
    assert d["actuals_floor_respected"] is True


# .LBN / .MAT never receive numeric staffing dollars
def test_lbn_and_mat_no_numeric_dollars():
    for cat, key in (("LBN", "1000.10-01-318.LBN"), ("MAT", "1000.10-01-318.MAT")):
        nf, nc, d = _apply(_base(category=cat, budget_code_key=key))
        assert d["staffing_basis_status"] == "not_applicable_no_accepted_lab_staffing_basis"
        assert nc == D("23145.65")   # model value unchanged


# accepted value-asserting model control wins over staffing
def test_model_control_wins_over_staffing():
    nf, nc, d = _apply(_base(operator_controlled=True))
    assert d["staffing_basis_status"] == "not_applicable_model_control_governs"
    assert nc == D("23145.65")


# dormant / closed suppression outranks staffing
def test_suppression_outranks_staffing():
    nf, nc, d = _apply(_base(suppressed=True))
    assert d["staffing_basis_status"] == "not_applicable_suppressed"
    assert nc == D("23145.65")


# material decrease is blocked unless explicit per-code dollar acceptance
def test_material_decrease_blocked_without_acceptance():
    nf, nc, d = _apply(_base(current_model_ctc="250931.13",
                             staffing_plan_implied_remaining_cost="206280.16",
                             staffing_plan_implied_final_cost="505660.45"))
    assert d["staffing_basis_status"] == "staffing_below_model_preserved"
    assert "pending_decrease_acceptance" in d["reason"][0]
    assert nc == D("250931.13")   # model preserved, NOT lowered


# explicit per-code dollar acceptance authorizes a decrease
def test_decrease_with_explicit_acceptance_applies():
    nf, nc, d = _apply(_base(current_model_ctc="250931.13",
                             staffing_plan_implied_remaining_cost="206280.16",
                             staffing_plan_implied_final_cost="505660.48",
                             operator_acceptance_status="accepted"))
    assert d["staffing_basis_status"] == "operator_staffing_plan_basis"
    assert nc == D("206280.16")


# unvalidated source or unaccepted mapping -> not applicable
def test_unvalidated_or_unaccepted_not_applicable():
    nf, nc, d = _apply(_base(staffing_source_validation_passed=False))
    assert d["staffing_basis_status"] == "not_applicable_no_accepted_lab_staffing_basis"
    nf, nc, d = _apply(_base(staffing_mapping_status="resolved_unique_lab_pending_acceptance"))
    assert d["staffing_basis_status"] == "not_applicable_no_accepted_lab_staffing_basis"


# validation gates pass over a consistent applied set
def test_validation_gates_pass():
    rows, totals = [], {}
    d = classify_staffing_basis(_base())
    mt = D(d["selected_cost_to_complete"])
    totals[d["budget_code_key"]] = mt
    rows.append(build_staffing_basis_audit_row(d, monthly_total_after_staffing_basis=mt))
    checks = validate_staffing_basis_decisions(rows, monthly_total_by_key=totals)
    assert all(checks.values()), [k for k, v in checks.items() if not v]
