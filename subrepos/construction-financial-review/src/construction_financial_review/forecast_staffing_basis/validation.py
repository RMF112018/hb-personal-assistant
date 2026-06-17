"""Fail-closed validation gates over staffing-basis decision rows."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import CENTS, D
from .classify import STATUS_OPERATOR_STAFFING_PLAN_BASIS

ZERO = Decimal("0")


def _d(v):
    return D(v) if v is not None else None


def validate_staffing_basis_decisions(rows, *, monthly_total_by_key=None):
    """`rows` are build_staffing_basis_audit_row outputs. Returns an OrderedDict of boolean gates."""
    monthly_total_by_key = monthly_total_by_key or {}
    applied = [r for r in rows if r["staffing_basis_status"] == STATUS_OPERATOR_STAFFING_PLAN_BASIS]

    # staffing_basis_reconciles: applied rows -> final == actual + ctc; ctc == implied remaining
    basis_ok = True
    for r in applied:
        actual = _d(r.get("actual_cost_to_date")) or ZERO
        final = _d(r.get("selected_final_cost"))
        ctc = _d(r.get("selected_cost_to_complete"))
        implied = _d(r.get("staffing_plan_implied_remaining_cost"))
        if final is None or ctc is None or implied is None:
            basis_ok = False
        elif abs(final - (actual + ctc)) > CENTS or abs(ctc - implied) > CENTS:
            basis_ok = False

    # monthly reconciles to selected CTC for applied rows we have a monthly total for
    monthly_ok = True
    for r in applied:
        mt = monthly_total_by_key.get(r["budget_code_key"])
        if mt is None:
            continue
        ctc = _d(r.get("selected_cost_to_complete"))
        if ctc is None or abs(D(mt) - ctc) > CENTS:
            monthly_ok = False

    # actuals floor: no selected final below actual cost to date
    floor_ok = all(
        (_d(r.get("selected_final_cost")) or ZERO) >= (_d(r.get("actual_cost_to_date")) or ZERO) - CENTS
        for r in rows)

    # LAB-only numeric application: every applied row is a .LAB code
    lab_only_ok = all(bool(r.get("is_lab")) for r in applied)
    # no .LBN / .MAT ever receives the staffing basis
    not_lbn_mat_ok = all(
        not str(r.get("budget_code_key") or "").upper().endswith((".LBN", ".MAT"))
        for r in applied)

    return OrderedDict([
        ("staffing_basis_reconciles", bool(basis_ok)),
        ("staffing_monthly_total_reconciles_to_selected_ctc", bool(monthly_ok)),
        ("staffing_actuals_floor_respected", bool(floor_ok)),
        ("staffing_lab_only_numeric_application", bool(lab_only_ok)),
        ("staffing_does_not_apply_to_lbn_or_mat", bool(not_lbn_mat_ok)),
    ])


__all__ = ["validate_staffing_basis_decisions"]
