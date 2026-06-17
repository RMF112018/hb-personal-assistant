"""Apply a cost-basis decision to an inbound (final, ctc) pair and build its audit row."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import CENTS, D, money_str
from .classify import (
    STATUS_BUDGETDETAILS_PROJECTED,
    STATUS_EXISTING_MODEL,
    STATUS_MANUAL_REVIEW,
    STATUS_OPERATOR_CONTROLLED,
    classify_budgetdetails_cost_basis,
)

ZERO = Decimal("0")

# statuses for which the decision OVERRIDES the inbound model (final, ctc); everything else keeps
# the inbound values untouched (existing model basis / operator / manual-review pass-through).
_OVERRIDING = {STATUS_BUDGETDETAILS_PROJECTED}
_SUPPRESSING = {"dormant_suppressed", "closed_suppressed", "recent_zero_run_suppressed",
                "suppressed_no_remaining_commitment"}


def apply_cost_basis_decision(inbound_final, inbound_ctc, actual, evidence: dict):
    """Return (new_final, new_ctc, decision).

    `evidence` is the flat dict consumed by classify_budgetdetails_cost_basis. The caller is
    responsible for the higher-precedence gating flags (operator_controlled / dormant_suppressed);
    only `budgetdetails_projected_cost_basis` (and the suppression/floor edges) change the dollars.
    """
    ev = dict(evidence)
    ev.setdefault("inbound_recommended_final", money_str(inbound_final))
    ev.setdefault("inbound_recommended_ctc", money_str(inbound_ctc))
    ev.setdefault("actual_cost_to_date", money_str(actual))
    decision = classify_budgetdetails_cost_basis(ev)

    status = decision["cost_basis_status"]
    new_final = D(inbound_final)
    new_ctc = D(inbound_ctc)
    # only budgetdetails basis and suppression statuses change the dollars; pass-through statuses
    # (existing model / operator / manual-review / floor disclosure) keep the inbound values.
    if status in _OVERRIDING or status in _SUPPRESSING:
        new_final = D(decision["selected_final_cost"])
        new_ctc = D(decision["selected_cost_to_complete"])
    return new_final, new_ctc, decision


def build_cost_basis_audit_row(decision: dict, *, monthly_total_after_basis=None) -> "OrderedDict":
    """Per-code audit row with formula evidence, selected basis, and monthly reconciliation."""
    actual = D(decision.get("actual_cost_to_date"))
    selected_final = D(decision.get("selected_final_cost"))
    row = OrderedDict([
        ("budget_code_key", decision.get("budget_code_key")),
        ("cost_code", decision.get("cost_code")),
        ("category", decision.get("category")),
        ("actual_cost_to_date", decision.get("actual_cost_to_date")),
        ("committed_costs", decision.get("committed_costs")),
        ("commitment_invoiced", decision.get("commitment_invoiced")),
        ("erp_direct_costs", decision.get("erp_direct_costs")),
        ("erp_job_to_date_costs", decision.get("erp_job_to_date_costs")),
        ("pending_cost_changes", decision.get("pending_cost_changes")),
        ("projected_costs", decision.get("projected_costs")),
        ("projected_cost_formula_value", decision.get("projected_cost_formula_value")),
        ("projected_cost_formula_reconciles", decision.get("projected_cost_formula_reconciles")),
        ("existing_model_final", decision.get("pre_cost_basis_model_final")),
        ("existing_model_ctc", decision.get("pre_cost_basis_model_ctc")),
        ("affirmative_remaining_evidence", decision.get("affirmative_remaining_evidence")),
        ("selected_final_cost", decision.get("selected_final_cost")),
        ("selected_cost_to_complete", decision.get("selected_cost_to_complete")),
        ("cost_basis_status", decision.get("cost_basis_status")),
        ("suppression_applied", decision.get("suppression_applied")),
        ("operator_controlled", decision.get("cost_basis_status") == STATUS_OPERATOR_CONTROLLED),
        ("floor_applied", decision.get("floor_applied")),
        ("monthly_total_after_basis",
         money_str(D(monthly_total_after_basis)) if monthly_total_after_basis is not None else None),
        ("reason", decision.get("reason")),
        ("validation_status", decision.get("validation_status")),
    ])
    if monthly_total_after_basis is not None:
        variance = (actual + D(monthly_total_after_basis)) - selected_final
        row["final_reconciliation_variance"] = money_str(variance)
    else:
        row["final_reconciliation_variance"] = None
    return row


def basis_disclosure_fields(decision: dict) -> "OrderedDict":
    """Compact disclosure fields stamped onto integrated forecast / recommendation rows."""
    return OrderedDict([
        ("cost_basis_status", decision.get("cost_basis_status")),
        ("selected_cost_basis", decision.get("selected_cost_basis")),
        ("projected_cost_formula_value", decision.get("projected_cost_formula_value")),
        ("projected_cost_formula_reconciles", decision.get("projected_cost_formula_reconciles")),
        ("cost_basis_floor_applied", decision.get("floor_applied")),
        ("cost_basis_reason", decision.get("reason")),
    ])


__all__ = ["apply_cost_basis_decision", "build_cost_basis_audit_row", "basis_disclosure_fields",
           "STATUS_EXISTING_MODEL", "STATUS_MANUAL_REVIEW"]
