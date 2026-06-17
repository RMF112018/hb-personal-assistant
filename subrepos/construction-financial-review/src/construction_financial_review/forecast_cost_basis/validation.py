"""Fail-closed validation checks over cost-basis decision rows.

Semantics (refinement #2): a present-but-non-reconciling projected-cost formula on a code that does
NOT use projected basis must not fail the package. Fail closed only when projected basis is actually
applied on a non-reconciling formula, or a selected-basis reconciliation gate fails.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import CENTS, D
from .classify import (
    STATUS_BUDGETDETAILS_PROJECTED,
    STATUS_OPERATOR_CONTROLLED,
    STATUS_SUPPRESSED_NO_REMAINING,
)

ZERO = Decimal("0")
SURVEY_CODE = "1000.15-01-426.MAT"
MANUAL_MONTHLY_CODE = "1000.15-16-110.SUB"


def _d(v):
    return D(v) if v is not None else None


def validate_cost_basis_decisions(rows, *, monthly_total_by_key=None) -> "OrderedDict":
    """`rows` are build_cost_basis_audit_row outputs. Returns an OrderedDict of boolean gates."""
    monthly_total_by_key = monthly_total_by_key or {}

    # projected-cost formula: only enforced where projected basis is actually applied.
    formula_ok = True
    for r in rows:
        if r["cost_basis_status"] == STATUS_BUDGETDETAILS_PROJECTED:
            if not r.get("projected_cost_formula_reconciles"):
                formula_ok = False

    # budgetdetails basis rows reconcile: final == projected, ctc == max(projected - actual, 0)
    basis_ok = True
    for r in rows:
        if r["cost_basis_status"] != STATUS_BUDGETDETAILS_PROJECTED:
            continue
        proj = _d(r.get("projected_costs"))
        final = _d(r.get("selected_final_cost"))
        ctc = _d(r.get("selected_cost_to_complete"))
        actual = _d(r.get("actual_cost_to_date")) or ZERO
        exp_ctc = max(proj - actual, ZERO) if proj is not None else None
        if proj is None or final is None or ctc is None or exp_ctc is None:
            basis_ok = False
        elif abs(final - proj) > CENTS or abs(ctc - exp_ctc) > CENTS:
            basis_ok = False

    # monthly reconciles to selected CTC for every code we have a monthly total for
    monthly_ok = True
    for r in rows:
        mt = monthly_total_by_key.get(r["budget_code_key"])
        if mt is None:
            continue
        ctc = _d(r.get("selected_cost_to_complete"))
        if ctc is None or abs(D(mt) - ctc) > CENTS:
            monthly_ok = False

    # zero-commitment suppression: ctc == 0, final == actual
    zero_supp_ok = all(
        _d(r.get("selected_cost_to_complete")) == ZERO
        and _d(r.get("selected_final_cost")) == (_d(r.get("actual_cost_to_date")) or ZERO)
        for r in rows if r["cost_basis_status"] == STATUS_SUPPRESSED_NO_REMAINING)

    # actuals floor: no selected final below actual cost to date
    floor_ok = all(
        (_d(r.get("selected_final_cost")) or ZERO) >= (_d(r.get("actual_cost_to_date")) or ZERO) - CENTS
        for r in rows)

    # accepted value-asserting operator controls are not overwritten by projected-cost basis
    operator_ok = all(r["cost_basis_status"] == STATUS_OPERATOR_CONTROLLED
                      for r in rows if r.get("operator_controlled"))

    # existing dormant/closed suppression preserved (suppressed rows -> ctc 0, final actual)
    suppression_statuses = {"dormant_suppressed", "closed_suppressed", "recent_zero_run_suppressed"}
    dorm_ok = all(
        _d(r.get("selected_cost_to_complete")) == ZERO
        and _d(r.get("selected_final_cost")) == (_d(r.get("actual_cost_to_date")) or ZERO)
        for r in rows if r["cost_basis_status"] in suppression_statuses)

    by_key = {r["budget_code_key"]: r for r in rows}
    survey = by_key.get(SURVEY_CODE)
    survey_ok = bool(
        survey
        and survey["cost_basis_status"] == STATUS_BUDGETDETAILS_PROJECTED
        and _d(survey.get("selected_final_cost")) == Decimal("52778.50")
        and _d(survey.get("selected_cost_to_complete")) == Decimal("25000.00")
        and (monthly_total_by_key.get(SURVEY_CODE) is None
             or abs(D(monthly_total_by_key[SURVEY_CODE]) - Decimal("25000.00")) <= CENTS)
    ) if survey is not None else True   # absent (e.g. unit fixtures) -> not applicable

    # manual_monthly 1000.15-16-110.SUB never falls under projected-cost basis
    manual = by_key.get(MANUAL_MONTHLY_CODE)
    manual_ok = (manual is None) or (manual["cost_basis_status"] != STATUS_BUDGETDETAILS_PROJECTED)

    return OrderedDict([
        ("projected_cost_formula_reconciles", bool(formula_ok)),
        ("budgetdetails_projected_cost_basis_reconciles", bool(basis_ok)),
        ("monthly_reconciles_to_selected_ctc", bool(monthly_ok)),
        ("zero_commitment_suppression_reconciles", bool(zero_supp_ok)),
        ("actuals_floor_respected", bool(floor_ok)),
        ("operator_controls_preserved", bool(operator_ok)),
        ("dormant_closed_suppression_preserved", bool(dorm_ok)),
        ("survey_code_1000_15_01_426_mat_projected_cost_basis", bool(survey_ok)),
        ("manual_monthly_1000_15_16_110_sub_preserved", bool(manual_ok)),
    ])


__all__ = ["validate_cost_basis_decisions"]
