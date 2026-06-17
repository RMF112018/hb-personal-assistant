"""Deterministic cost-basis selection for the construction forecast pipeline.

Decides, per budget code, which deterministic cost basis governs the selected final cost and
cost-to-complete: accepted operator controls, dormant/closed/recent-zero suppression, zero-remaining
suppression, the BudgetDetails projected-cost basis (evidence-based, NEVER a hidden probability cap),
or the existing model basis.

The BudgetDetails projected-cost basis is *asymmetric / corrective*: it may RAISE a proven
under-forecast up to ERP `projected_costs` when open committed exposure is missed, but it must NEVER
lower a model-supported overrun down to ERP (that would violate the never-cap-at-ERP invariant).
"""
from .classify import (
    STATUS_BUDGETDETAILS_PROJECTED,
    STATUS_CLOSED_SUPPRESSED,
    STATUS_DORMANT_SUPPRESSED,
    STATUS_EXISTING_MODEL,
    STATUS_MANUAL_REVIEW,
    STATUS_OPERATOR_CONTROLLED,
    STATUS_RECENT_ZERO_RUN_SUPPRESSED,
    STATUS_SUPPRESSED_NO_REMAINING,
    classify_budgetdetails_cost_basis,
)
from .apply import apply_cost_basis_decision, build_cost_basis_audit_row
from .validation import validate_cost_basis_decisions

__all__ = [
    "classify_budgetdetails_cost_basis",
    "apply_cost_basis_decision",
    "build_cost_basis_audit_row",
    "validate_cost_basis_decisions",
    "STATUS_OPERATOR_CONTROLLED",
    "STATUS_DORMANT_SUPPRESSED",
    "STATUS_CLOSED_SUPPRESSED",
    "STATUS_RECENT_ZERO_RUN_SUPPRESSED",
    "STATUS_SUPPRESSED_NO_REMAINING",
    "STATUS_BUDGETDETAILS_PROJECTED",
    "STATUS_EXISTING_MODEL",
    "STATUS_MANUAL_REVIEW",
]
