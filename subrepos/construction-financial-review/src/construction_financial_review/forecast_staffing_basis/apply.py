"""Apply a staffing-basis decision to an inbound (final, ctc) pair and build its audit row."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, money_str
from .classify import STATUS_OPERATOR_STAFFING_PLAN_BASIS, classify_staffing_basis

ZERO = Decimal("0")


def apply_staffing_basis_decision(inbound_final, inbound_ctc, actual, evidence: dict):
    """Return (new_final, new_ctc, decision).

    Only `operator_staffing_plan_basis` changes the inbound dollars; every other status is a
    pass-through that keeps the inbound (model/operator/suppressed) values.
    """
    ev = dict(evidence)
    ev.setdefault("current_model_final", money_str(inbound_final))
    ev.setdefault("current_model_ctc", money_str(inbound_ctc))
    ev.setdefault("actual_cost_to_date", money_str(actual))
    decision = classify_staffing_basis(ev)

    new_final, new_ctc = D(inbound_final), D(inbound_ctc)
    if decision["staffing_basis_status"] == STATUS_OPERATOR_STAFFING_PLAN_BASIS:
        new_final = D(decision["selected_final_cost"])
        new_ctc = D(decision["selected_cost_to_complete"])
    return new_final, new_ctc, decision


def build_staffing_basis_audit_row(decision: dict, *, monthly_total_after_staffing_basis=None):
    actual = D(decision.get("actual_cost_to_date"))
    selected_final = D(decision.get("selected_final_cost"))
    row = OrderedDict([
        ("budget_code_key", decision.get("budget_code_key")),
        ("cost_code", decision.get("cost_code")),
        ("category", decision.get("category")),
        ("is_lab", decision.get("is_lab")),
        ("actual_cost_to_date", decision.get("actual_cost_to_date")),
        ("current_model_final_cost", decision.get("current_model_final_cost")),
        ("current_model_cost_to_complete", decision.get("current_model_cost_to_complete")),
        ("staffing_plan_implied_final_cost", decision.get("staffing_plan_implied_final_cost")),
        ("staffing_plan_implied_remaining_cost", decision.get("staffing_plan_implied_remaining_cost")),
        ("delta_vs_model_final", decision.get("delta_vs_model_final")),
        ("delta_vs_model_ctc", decision.get("delta_vs_model_ctc")),
        ("staffing_mapping_status", decision.get("staffing_mapping_status")),
        ("staffing_source_validation_passed", decision.get("staffing_source_validation_passed")),
        ("staffing_basis_status", decision.get("staffing_basis_status")),
        ("selected_final_cost", decision.get("selected_final_cost")),
        ("selected_cost_to_complete", decision.get("selected_cost_to_complete")),
        ("monthly_total_after_staffing_basis",
         money_str(D(monthly_total_after_staffing_basis))
         if monthly_total_after_staffing_basis is not None else None),
        ("operator_acceptance_status", decision.get("operator_acceptance_status")),
        ("actuals_floor_respected", decision.get("actuals_floor_respected")),
        ("reason", decision.get("reason")),
        ("validation_status", decision.get("validation_status")),
    ])
    if monthly_total_after_staffing_basis is not None:
        variance = (actual + D(monthly_total_after_staffing_basis)) - selected_final
        row["final_reconciliation_variance"] = money_str(variance)
    else:
        row["final_reconciliation_variance"] = None
    return row


def staffing_disclosure_fields(decision: dict):
    """Compact disclosure stamped onto integrated forecast / recommendation rows."""
    return OrderedDict([
        ("staffing_basis_status", decision.get("staffing_basis_status")),
        ("staffing_basis_applied", decision.get("staffing_basis_applied")),
        ("staffing_plan_implied_remaining_cost", decision.get("staffing_plan_implied_remaining_cost")),
        ("staffing_basis_reason", decision.get("reason")),
    ])


__all__ = ["apply_staffing_basis_decision", "build_staffing_basis_audit_row",
           "staffing_disclosure_fields"]
