"""Pure deterministic staffing-plan cost-basis classification.

`classify_staffing_basis(inp)` consumes a flat per-code dict and returns an OrderedDict decision.
Side-effect free, Decimal-exact. The caller supplies the higher-precedence gating flags
(`operator_controlled` from an accepted value-asserting model control, `suppressed` from
dormant/closed/recent-zero) — both outrank staffing.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import CENTS, dec, money_str

ZERO = Decimal("0")

STATUS_OPERATOR_STAFFING_PLAN_BASIS = "operator_staffing_plan_basis"
STATUS_STAFFING_BELOW_MODEL_PRESERVED = "staffing_below_model_preserved"
STATUS_MODEL_CONTROL_GOVERNS = "not_applicable_model_control_governs"
STATUS_SUPPRESSED = "not_applicable_suppressed"
STATUS_NOT_APPLICABLE = "not_applicable_no_accepted_lab_staffing_basis"

ACCEPTED_LAB_MAPPING = "mapped_operator_approved_lab"


def _d(inp, key):
    return dec(inp.get(key))


def _is_lab(inp) -> bool:
    cat = inp.get("category")
    if cat:
        return str(cat).upper() == "LAB"
    key = inp.get("budget_code_key") or ""
    return key.upper().endswith(".LAB")


def classify_staffing_basis(inp: dict) -> "OrderedDict[str, object]":
    actual = _d(inp, "actual_cost_to_date") or ZERO
    model_final = _d(inp, "current_model_final")
    model_ctc = _d(inp, "current_model_ctc")
    if model_final is None:
        model_final = actual
    if model_ctc is None:
        model_ctc = ZERO

    implied_remaining = _d(inp, "staffing_plan_implied_remaining_cost")
    implied_final = _d(inp, "staffing_plan_implied_final_cost")
    is_lab = _is_lab(inp)
    mapping_status = inp.get("staffing_mapping_status")
    applied_numeric = bool(inp.get("staffing_applied_numeric"))
    source_validated = bool(inp.get("staffing_source_validation_passed"))
    accept_status = inp.get("operator_acceptance_status")  # per-code dollar acceptance (decrease gate)

    delta_ctc = (implied_remaining - model_ctc) if implied_remaining is not None else None
    delta_final = (implied_final - model_final) if implied_final is not None else None

    out = OrderedDict([
        ("budget_code_key", inp.get("budget_code_key")),
        ("cost_code", inp.get("cost_code")),
        ("category", inp.get("category")),
        ("is_lab", is_lab),
        ("actual_cost_to_date", money_str(actual)),
        ("current_model_final_cost", money_str(model_final)),
        ("current_model_cost_to_complete", money_str(model_ctc)),
        ("staffing_plan_implied_final_cost", money_str(implied_final) if implied_final is not None else None),
        ("staffing_plan_implied_remaining_cost",
         money_str(implied_remaining) if implied_remaining is not None else None),
        ("delta_vs_model_final", money_str(delta_final) if delta_final is not None else None),
        ("delta_vs_model_ctc", money_str(delta_ctc) if delta_ctc is not None else None),
        ("staffing_mapping_status", mapping_status),
        ("staffing_applied_numeric", applied_numeric),
        ("staffing_source_validation_passed", source_validated),
        ("operator_acceptance_status", accept_status),
    ])

    def _finish(status, final, ctc, *, reason, floor_ok=True, applied=False, validation="ok"):
        out["staffing_basis_status"] = status
        out["selected_final_cost"] = money_str(final)
        out["selected_cost_to_complete"] = money_str(ctc)
        out["actuals_floor_respected"] = bool(final >= actual - CENTS)
        out["staffing_basis_applied"] = bool(applied)
        out["reason"] = reason if isinstance(reason, list) else [reason]
        out["validation_status"] = validation
        return out

    # higher-precedence gates (caller-supplied): model controls and suppression outrank staffing
    if inp.get("operator_controlled"):
        return _finish(STATUS_MODEL_CONTROL_GOVERNS, model_final, model_ctc,
                       reason="accepted_model_control_governs_staffing_not_applied")
    if inp.get("suppressed"):
        return _finish(STATUS_SUPPRESSED, model_final, model_ctc,
                       reason="dormant_or_closed_suppression_governs_staffing_not_applied")

    # eligibility: mapped .LAB numeric target, operator-approved mapping, validated staffing source
    eligible = bool(is_lab and applied_numeric and mapping_status == ACCEPTED_LAB_MAPPING
                    and source_validated and implied_remaining is not None)
    if not eligible:
        return _finish(STATUS_NOT_APPLICABLE, model_final, model_ctc,
                       reason="no_accepted_lab_mapping_or_unvalidated_staffing_source")

    # raise-only: staffing may raise an under-forecast; a decrease needs explicit per-code acceptance
    if delta_ctc is not None and delta_ctc > CENTS:
        sel_final = actual + implied_remaining
        return _finish(STATUS_OPERATOR_STAFFING_PLAN_BASIS, sel_final, implied_remaining, applied=True,
                       reason="operator_approved_lab_mapping_validated_staffing_source_raise_only")
    if accept_status == "accepted":
        # explicit per-code operator dollar acceptance authorizes a material decrease
        sel_final = actual + implied_remaining
        return _finish(STATUS_OPERATOR_STAFFING_PLAN_BASIS, sel_final, implied_remaining, applied=True,
                       reason="operator_accepted_staffing_dollar_basis_decrease")
    # decrease/equal without explicit acceptance: preserve model (no silent downward cap)
    return _finish(STATUS_STAFFING_BELOW_MODEL_PRESERVED, model_final, model_ctc,
                   reason="staffing_plan_below_model_preserved_pending_decrease_acceptance")
