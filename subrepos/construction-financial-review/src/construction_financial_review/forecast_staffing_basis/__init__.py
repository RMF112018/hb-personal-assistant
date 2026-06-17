"""Deterministic operator staffing-plan cost basis for mapped `.LAB` budget codes.

When the operator has approved the staffing cost-code mapping (`mapped_operator_approved_lab`) and the
staffing source is validated, the operator-planned remaining labor is an *accepted dollar basis* — not
merely a monthly timing shape and not a model inference. This layer selects, per `.LAB` code, the
staffing-plan CTC as the deterministic basis when it RAISES a model under-forecast.

Asymmetric / raise-only: staffing may raise an under-forecasted `.LAB` code up to the operator-planned
remaining; it never silently lowers a model-supported forecast — a material decrease requires explicit
per-code operator dollar acceptance. `.LBN`/`.MAT` never receive numeric staffing dollars (date-context
only). Forecast-model controls and dormant/closed/recent-zero suppression both outrank staffing.
"""
from .classify import (
    STATUS_MODEL_CONTROL_GOVERNS,
    STATUS_NOT_APPLICABLE,
    STATUS_OPERATOR_STAFFING_PLAN_BASIS,
    STATUS_STAFFING_BELOW_MODEL_PRESERVED,
    STATUS_SUPPRESSED,
    classify_staffing_basis,
)
from .apply import (
    apply_staffing_basis_decision,
    build_staffing_basis_audit_row,
    staffing_disclosure_fields,
)
from .validation import validate_staffing_basis_decisions

__all__ = [
    "classify_staffing_basis",
    "apply_staffing_basis_decision",
    "build_staffing_basis_audit_row",
    "staffing_disclosure_fields",
    "validate_staffing_basis_decisions",
    "STATUS_OPERATOR_STAFFING_PLAN_BASIS",
    "STATUS_STAFFING_BELOW_MODEL_PRESERVED",
    "STATUS_MODEL_CONTROL_GOVERNS",
    "STATUS_SUPPRESSED",
    "STATUS_NOT_APPLICABLE",
]
