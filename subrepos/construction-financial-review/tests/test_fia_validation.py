"""Fail-closed validation-gate helper tests (cap governance)."""
from construction_financial_review.forecast_improvement_audit import validation as v


def _fee_row(**over):
    base = {"budget_code_key": "1000.20-18-110.OVH", "fee_cap_basis": "projected_budget_value",
            "fee_projected_budget_cap_value": "100000.00", "evidence_supported_fee_before_cap": "150000.00",
            "fee_forecast_after_cap": "100000.00", "fee_projected_budget_cap_applied": True,
            "actuals_exceed_fee_cap_exception": False, "actual_fee_cost_to_date": "0.00"}
    base.update(over)
    return base


def test_fee_cap_enforced_passes_when_capped():
    assert v.fee_cap_enforced([_fee_row()]) is True


def test_fee_cap_enforced_fails_when_left_uncapped():
    # evidence over cap, no exception, but after exceeds cap and not applied -> violation
    bad = _fee_row(fee_forecast_after_cap="150000.00", fee_projected_budget_cap_applied=False)
    assert v.fee_cap_enforced([bad]) is False


def test_fee_cap_enforced_actuals_exception_ok():
    ok = _fee_row(actual_fee_cost_to_date="200000.00", fee_forecast_after_cap="200000.00",
                  actuals_exceed_fee_cap_exception=True, fee_projected_budget_cap_applied=False)
    assert v.fee_cap_enforced([ok]) is True


def test_fee_floor_preserved():
    assert v.fee_floor_preserved([_fee_row()]) is True
    assert v.fee_floor_preserved([_fee_row(fee_forecast_after_cap="0.00",
                                           actual_fee_cost_to_date="5.00")]) is False


def test_fee_basis_correct():
    assert v.fee_basis_correct([_fee_row()]) is True
    assert v.fee_basis_correct([_fee_row(fee_cap_basis="revised_budget")]) is False
    assert v.fee_basis_correct([{"fee_cap_basis": "none",
                                 "fee_projected_budget_cap_value": "100"}]) is False


def test_non_fee_has_no_cap():
    assert v._non_fee_has_no_cap([{"some_cap_applied": False}]) is True
    assert v._non_fee_has_no_cap([{"projected_budget_cap_applied": True}]) is False  # non-fee cap -> fail
    assert v._non_fee_has_no_cap([{"fee_projected_budget_cap_applied": True}]) is True  # fee_ allowed
