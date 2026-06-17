"""Pure deterministic cost-basis classification.

`classify_budgetdetails_cost_basis(inp)` consumes a flat dict of per-code evidence and returns an
OrderedDict decision. It is side-effect free and Decimal-exact, so it is safe to call from both the
intelligence layer (operator controls not yet known) and the comprehensive layer (operator controls
and suppression known) — the comprehensive call is the authoritative one.

Precedence (highest first):
  1. accepted value-asserting operator controls            -> operator_controlled
  2. dormant / closed / recent-zero-run suppression        -> *_suppressed
  3. an upstream-applied budgetdetails basis (idempotent)  -> budgetdetails_projected_cost_basis
  4. committed exposure + reconciling formula, asymmetric  -> budgetdetails_projected_cost_basis
     (only when projected_costs > ORIGINAL pre-basis model final; never lowers an overrun)
  5. zero committed + no affirmative remaining evidence     -> suppressed_no_remaining_commitment
  6. fall back                                              -> existing_model_basis
A present-but-non-reconciling projected-cost formula never yields projected basis -> manual_review_required.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import CENTS, dec, money_str

ZERO = Decimal("0")

STATUS_OPERATOR_CONTROLLED = "operator_controlled"
STATUS_DORMANT_SUPPRESSED = "dormant_suppressed"
STATUS_CLOSED_SUPPRESSED = "closed_suppressed"
STATUS_RECENT_ZERO_RUN_SUPPRESSED = "recent_zero_run_suppressed"
STATUS_SUPPRESSED_NO_REMAINING = "suppressed_no_remaining_commitment"
STATUS_BUDGETDETAILS_PROJECTED = "budgetdetails_projected_cost_basis"
STATUS_EXISTING_MODEL = "existing_model_basis"
STATUS_MANUAL_REVIEW = "manual_review_required"

# dormant_status values (from forecast_dormancy.classify) that map to suppression sub-statuses
_DORMANT_STATUS_MAP = {
    "closed_do_not_use": STATUS_CLOSED_SUPPRESSED,
    "recent_zero_run_after_prior_activity": STATUS_RECENT_ZERO_RUN_SUPPRESSED,
}

_FORMULA_FIELDS = ("committed_costs", "erp_direct_costs", "pending_cost_changes", "projected_costs")
_AMOUNT_FIELDS = _FORMULA_FIELDS + (
    "commitment_invoiced", "erp_job_to_date_costs", "estimated_cost_at_completion",
    "forecast_to_complete", "revised_budget", "projected_budget",
)


def _d(inp, key):
    return dec(inp.get(key))


def classify_budgetdetails_cost_basis(inp: dict) -> "OrderedDict[str, object]":
    actual = _d(inp, "actual_cost_to_date") or ZERO
    # ORIGINAL model output (before any cost-basis selection) drives the asymmetric guard.
    model_final = _d(inp, "pre_cost_basis_model_final")
    model_ctc = _d(inp, "pre_cost_basis_model_ctc")
    # inbound values may already carry an upstream basis; default to the pre-basis model values.
    inbound_final = _d(inp, "inbound_recommended_final")
    inbound_ctc = _d(inp, "inbound_recommended_ctc")
    if model_final is None:
        model_final = inbound_final if inbound_final is not None else actual
    if model_ctc is None:
        model_ctc = inbound_ctc if inbound_ctc is not None else ZERO
    if inbound_final is None:
        inbound_final = model_final
    if inbound_ctc is None:
        inbound_ctc = model_ctc

    committed = _d(inp, "committed_costs")
    erp_direct = _d(inp, "erp_direct_costs")
    pending = _d(inp, "pending_cost_changes")
    projected = _d(inp, "projected_costs")

    formula_present = all(inp.get(f) is not None for f in _FORMULA_FIELDS)
    formula_value = (committed + erp_direct + pending) if formula_present else None
    formula_reconciles = bool(formula_present and abs(projected - formula_value) <= CENTS)

    # structured, auditable affirmative remaining-cost evidence (refinement #3)
    integrated_ctc = _d(inp, "integrated_model_ctc")
    ev = OrderedDict([
        ("has_model_remaining_ctc", bool(model_ctc is not None and model_ctc > CENTS)),
        ("has_integrated_remaining_ctc", bool(integrated_ctc is not None and integrated_ctc > CENTS)),
        ("has_schedule_remaining_evidence", bool(inp.get("has_schedule_remaining_evidence"))),
        ("has_trend_or_burn_evidence", bool(inp.get("has_trend_or_burn_evidence"))),
        ("has_recent_actual_activity", bool(inp.get("has_recent_actual_activity"))),
        ("has_staffing_remaining_evidence", bool(inp.get("has_staffing_remaining_evidence"))),
        ("has_positive_operator_monthly_shape", bool(inp.get("has_positive_operator_monthly_shape"))),
        ("has_value_asserting_operator_control", bool(inp.get("has_value_asserting_operator_control"))),
    ])
    affirmative_remaining_evidence = any(ev.values())

    out = OrderedDict()
    out["budget_code_key"] = inp.get("budget_code_key")
    out["cost_code"] = inp.get("cost_code")
    out["category"] = inp.get("category")
    out["actual_cost_to_date"] = money_str(actual)
    for f in _AMOUNT_FIELDS:
        out[f] = money_str(_d(inp, f)) if inp.get(f) is not None else None
    out["projected_cost_formula_value"] = money_str(formula_value) if formula_value is not None else None
    out["projected_cost_formula_reconciles"] = formula_reconciles
    out["pre_cost_basis_model_final"] = money_str(model_final)
    out["pre_cost_basis_model_ctc"] = money_str(model_ctc)
    out.update(ev)
    out["affirmative_remaining_evidence"] = affirmative_remaining_evidence

    def _finish(status, final, ctc, *, reason, floor=False, suppression=False,
                operator=False, validation="ok", basis=None):
        out["cost_basis_status"] = status
        out["selected_cost_basis"] = basis or status
        out["selected_final_cost"] = money_str(final)
        out["selected_cost_to_complete"] = money_str(ctc)
        out["floor_applied"] = bool(floor)
        out["suppression_applied"] = bool(suppression)
        out["operator_override_applied"] = bool(operator)
        out["reason"] = reason if isinstance(reason, list) else [reason]
        out["validation_status"] = validation
        return out

    # 1. accepted value-asserting operator controls win (caller-gated)
    if inp.get("operator_controlled"):
        return _finish(STATUS_OPERATOR_CONTROLLED, inbound_final, inbound_ctc,
                       reason="accepted_operator_control_governs", operator=True)

    # 2. dormant / closed / recent-zero-run suppression remains authoritative
    if inp.get("dormant_suppressed"):
        status = _DORMANT_STATUS_MAP.get(inp.get("dormant_status"), STATUS_DORMANT_SUPPRESSED)
        return _finish(status, actual, ZERO, reason=["suppression_authoritative",
                       inp.get("dormant_status") or "dormant"], suppression=True)

    # 2b. an operator staffing-plan basis already governs (precedence 3 > 4): pass through its values,
    # never override with the BudgetDetails projected-cost basis.
    if inp.get("staffing_basis_applied"):
        return _finish(STATUS_EXISTING_MODEL, inbound_final, inbound_ctc,
                       reason="operator_staffing_plan_basis_governs")

    # 3. idempotency: preserve an upstream-applied budgetdetails basis even if inbound now == projected
    if inp.get("upstream_cost_basis_status") == STATUS_BUDGETDETAILS_PROJECTED and projected is not None:
        ctc = projected - actual
        return _finish(STATUS_BUDGETDETAILS_PROJECTED, projected, ctc if ctc > ZERO else ZERO,
                       reason=["upstream_budgetdetails_basis_preserved", "projected_cost_formula_reconciles"])

    # Pass-through (non-overriding) statuses keep the INBOUND values that actually flow downstream
    # (already history/operator/dormancy-adjusted) — NOT the raw model values — so the audit's
    # selected CTC matches what monthly reconciles to.
    # 4. committed exposure path
    if committed is not None and committed > ZERO:
        if not formula_reconciles:
            # present-but-non-reconciling formula: never use projected basis (refinement #2)
            return _finish(STATUS_MANUAL_REVIEW, inbound_final, inbound_ctc,
                           reason="projected_cost_formula_mismatch", validation="manual_review")
        if projected < actual:
            # ERP total below actuals already spent: defensive floor disclosure; keep inbound values
            # (model is itself >= actual). Never forces a model overrun down to ERP/actuals.
            return _finish(STATUS_EXISTING_MODEL, inbound_final, inbound_ctc,
                           reason=["projected_cost_below_actuals", "actuals_floor_preserved"],
                           floor=True)
        if projected > model_final + CENTS:
            # asymmetric / corrective: raise the proven under-forecast to ERP projected cost
            ctc = projected - actual
            return _finish(STATUS_BUDGETDETAILS_PROJECTED, projected, ctc if ctc > ZERO else ZERO,
                           reason=["committed_remaining_exposure", "projected_cost_formula_reconciles"])
        # model already at/above projected: never cap an overrun down to ERP
        return _finish(STATUS_EXISTING_MODEL, inbound_final, inbound_ctc,
                       reason="model_final_above_projected_costs_preserved_no_erp_cap")

    # 5. zero committed cost
    if committed is not None and committed <= ZERO and not affirmative_remaining_evidence:
        return _finish(STATUS_SUPPRESSED_NO_REMAINING, actual, ZERO,
                       reason="committed_zero_and_no_remaining_evidence", suppression=True)
    if committed is not None and committed <= ZERO:
        return _finish(STATUS_EXISTING_MODEL, inbound_final, inbound_ctc,
                       reason="committed_zero_but_model_remaining_evidence_preserved")

    # 6. fall back to existing model basis
    return _finish(STATUS_EXISTING_MODEL, inbound_final, inbound_ctc, reason="existing_model_basis")
