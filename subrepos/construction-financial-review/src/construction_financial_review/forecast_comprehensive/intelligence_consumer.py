"""Integrated final-cost recommendation: accepted intelligence base + bounded advisory evidence.

Accepted forecast-intelligence `recommended_final_cost` is the BASE. History-informed final cost is one
advisory family, consumed at a bounded, contradiction-collapsed weight. Cost-frequency carries ZERO
final-cost weight (timing only). The integrated final is floored at actual cost to date and NEVER capped
by any reference (budget / commitment / owner SOV / ERP / pay-app / prior forecast / probability).
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, money_str
from ..forecast_cost_basis import apply as cost_basis
from ..forecast_staffing_basis import apply as staffing_basis
from . import human_acceptance as ha

ZERO, ONE = Decimal("0"), Decimal("1")


def _staffing_basis_evidence(key, cost_code, entry, operator_controlled, dormant_suppressed,
                             integ_final, integ_ctc):
    """Assemble the flat evidence dict consumed by the staffing-basis classifier.

    current_model_final/ctc are the inbound integrated values (post operator/dormancy); the staffing
    summary row + mapping/source gating signals come from per_code (the discovered staffing package).
    """
    sp = entry.get("staffing_plan") or {}
    return {
        "budget_code_key": key,
        "cost_code": cost_code,
        "category": entry.get("category") or (key.split(".")[-1] if "." in key else None),
        "current_model_final": money_str(integ_final),
        "current_model_ctc": money_str(integ_ctc),
        "staffing_plan_implied_remaining_cost": sp.get("staffing_plan_implied_remaining_cost"),
        "staffing_plan_implied_final_cost": sp.get("staffing_plan_implied_final_cost"),
        "operator_acceptance_status": sp.get("acceptance_status"),
        "staffing_mapping_status": entry.get("staffing_mapping_status"),
        "staffing_applied_numeric": entry.get("staffing_applied_numeric"),
        "staffing_source_validation_passed": entry.get("staffing_source_validation_passed"),
        "operator_controlled": bool(operator_controlled),
        "suppressed": bool(dormant_suppressed),
    }


def _cost_basis_evidence(key, entry, rec, mdecision, operator_dollar, operator_model_value,
                         dormant, dormant_suppressed, integ_ctc):
    """Assemble the flat evidence dict consumed by the cost-basis classifier.

    pre_cost_basis_model_final/ctc are the ORIGINAL model outputs (before any basis selection) so the
    asymmetric guard compares projected against the real model number, not an already-raised value.
    """
    rec = rec or {}
    pre_final = rec.get("pre_cost_basis_model_final", rec.get("recommended_final_cost"))
    pre_ctc = rec.get("pre_cost_basis_model_ctc", rec.get("recommended_cost_to_complete"))
    op_monthly = bool(mdecision and (mdecision.get("monthly_allocation") or {}))
    ev = {
        "budget_code_key": key,
        "cost_code": key.split(".")[1] if "." in key else None,
        "category": entry.get("category") or (key.split(".")[-1] if "." in key else None),
        "pre_cost_basis_model_final": pre_final,
        "pre_cost_basis_model_ctc": pre_ctc,
        "integrated_model_ctc": money_str(integ_ctc),
        "upstream_cost_basis_status": rec.get("cost_basis_status"),
        "operator_controlled": bool(operator_dollar or operator_model_value),
        "dormant_suppressed": bool(dormant_suppressed),
        "dormant_status": (dormant or {}).get("dormant_status"),
        "has_schedule_remaining_evidence": bool(entry.get("sched")),
        "has_recent_actual_activity": bool(rec.get("actuals_month_count_nonzero")),
        "has_positive_operator_monthly_shape": op_monthly,
        "has_value_asserting_operator_control": bool(operator_model_value),
    }
    for f in ("committed_costs", "commitment_invoiced", "erp_direct_costs", "erp_job_to_date_costs",
              "pending_cost_changes", "projected_costs", "estimated_cost_at_completion",
              "forecast_to_complete", "revised_budget", "projected_budget"):
        ev[f] = entry.get(f)
    return ev


def build(project_key, key, entry, sc) -> tuple:
    """Return (forecast_row, final_cost_rec, floor_audit_row, integ_final, integ_ctc, cost_basis_decision)."""
    rec = entry["rec"]
    cost_code = key.split(".")[1] if "." in key else None
    actual_floor = D(entry["actual_cost_to_date"])
    accepted_final = D(rec.get("recommended_final_cost")) if rec else actual_floor
    accepted_ctc = D(rec.get("recommended_cost_to_complete")) if rec else ZERO

    w = sc["history_final_cost_weight"]
    hadj = entry["hist_adj"]
    hist_final = D(hadj.get("history_informed_adjusted_final_cost")) if (hadj and w > 0) else accepted_final
    blended = accepted_final * (ONE - w) + hist_final * w
    integrated_final = blended if blended > actual_floor else actual_floor   # floor; never cap
    floored = integrated_final == actual_floor and blended < actual_floor
    integrated_ctc = integrated_final - actual_floor
    if integrated_ctc < ZERO:
        integrated_ctc = ZERO

    # operator forecast control: an ACCEPTED dollar control (remaining allowance / final override)
    # changes the integrated final cost; floored at actuals; recorded as an operator decision, not model
    # evidence. Timing-only stop-date controls do NOT change the dollar total here.
    decision = entry.get("operator_control")
    operator_dollar = bool(decision and decision.get("dollar_applied"))
    if operator_dollar:
        from ..forecast_controls.apply import effective_ctc
        new_ctc, _, _ = effective_ctc(accepted_ctc, accepted_ctc, actual_floor, decision)
        integrated_ctc = new_ctc if new_ctc > ZERO else ZERO
        integrated_final = actual_floor + integrated_ctc
        floored = integrated_final == actual_floor and new_ctc <= ZERO

    # operator forecast-MODEL control: the highest-priority explicit operator decision. A value-changing
    # control (equality / cap-that-binds / explicit total / manual totals) sets the integrated final cost
    # directly (floored at actuals, never a cap). Window/shape-only controls leave the dollar total
    # model-derived. Disclosed as an operator decision, not model evidence.
    mdecision = entry.get("model_control")
    operator_model_value = bool(mdecision and mdecision.get("changes_deterministic_final"))
    if operator_model_value:
        cf = D(mdecision["controlled_final_cost"])
        if cf < actual_floor:
            cf = actual_floor
        integrated_final = cf
        integrated_ctc = cf - actual_floor
        if integrated_ctc < ZERO:
            integrated_ctc = ZERO
        floored = integrated_final == actual_floor and D(mdecision["controlled_final_cost"]) <= actual_floor

    # dormant / closed-code suppression (defensive enforcement of the authoritative intelligence decision):
    # a suppressed code's integrated final stays at actual cost to date (CTC=0) so the history blend cannot
    # re-inflate it. Overridden ONLY by a value-asserting operator model control that asserts positive
    # remaining (controlled_remaining > 0); shape/window/timing-only controls do not revive a dormant code.
    dormant = entry.get("dormant")
    op_value_assert = bool(mdecision and mdecision.get("changes_deterministic_final")
                           and D(mdecision.get("controlled_remaining")) > ZERO)
    dormant_suppressed = bool(dormant and dormant.get("suppression_applied") and not op_value_assert)
    if dormant_suppressed:
        integrated_final = actual_floor
        integrated_ctc = ZERO
        floored = True

    # Operator staffing-plan basis (mapped .LAB, raise-only): AFTER operator controls + dormancy, BEFORE
    # the BudgetDetails basis (precedence 3 > 4). When the operator-approved LAB mapping + validated
    # staffing source prove planned remaining labor above the model CTC, the staffing-plan remaining is
    # the selected deterministic basis. Never lowers a model-supported forecast without explicit per-code
    # dollar acceptance; .LBN/.MAT never get numeric dollars.
    operator_controlled = bool(operator_dollar or operator_model_value)
    sb_ev = _staffing_basis_evidence(key, cost_code, entry, operator_controlled, dormant_suppressed,
                                     integrated_final, integrated_ctc)
    integrated_final, integrated_ctc, sb_decision = staffing_basis.apply_staffing_basis_decision(
        integrated_final, integrated_ctc, actual_floor, sb_ev)
    staffing_basis_applied = bool(sb_decision.get("staffing_basis_applied"))
    if staffing_basis_applied:
        floored = False
    sb_fields = staffing_basis.staffing_disclosure_fields(sb_decision)

    # BudgetDetails projected-cost basis (asymmetric / corrective): authoritative AFTER operator
    # controls + dormancy + staffing. It may RAISE a proven under-forecast up to ERP projected_costs when
    # open committed exposure is missed; it NEVER lowers a model-supported overrun to ERP. Disclosed as a
    # deterministic evidence-based basis, never a hidden probability cap (upper_cap_applied stays False).
    cb_ev = _cost_basis_evidence(key, entry, rec, mdecision, operator_dollar, operator_model_value,
                                 dormant, dormant_suppressed, integrated_ctc)
    cb_ev["staffing_basis_applied"] = staffing_basis_applied
    integrated_final, integrated_ctc, cb_decision = cost_basis.apply_cost_basis_decision(
        integrated_final, integrated_ctc, actual_floor, cb_ev)
    if cb_decision["cost_basis_status"] == "budgetdetails_projected_cost_basis":
        floored = False
    delta = integrated_final - accepted_final
    cb_fields = cost_basis.basis_disclosure_fields(cb_decision)

    evidence_summary = OrderedDict([
        ("forecast_intelligence", "accepted_base"),
        ("history_informed_final_cost", sc["history_consumption_status"]),
        ("cost_frequency_cadence", "timing_only_zero_final_cost_weight"),
        ("forecast_probability", sc["probability_consumption_status"]),
        ("cost_entry_trend", "primary_truth_input"),
        ("schedule_remaining_work", sc["schedule_consumption_status"]),
        ("pay_application", sc["pay_app_consumption_status"]),
    ])

    forecast_row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("actual_cost_to_date", money_str(actual_floor)),
        ("accepted_recommended_final_cost", money_str(accepted_final)),
        ("accepted_recommended_cost_to_complete", money_str(accepted_ctc)),
        ("integrated_recommended_final_cost", money_str(integrated_final)),
        ("integrated_cost_to_complete", money_str(integrated_ctc)),
        ("integrated_minus_accepted_final_cost", money_str(delta)),
        ("history_final_cost_weight", str(w.quantize(Decimal("0.0001")))),
        ("frequency_final_cost_weight", "0.0000"),
        ("floored_at_actuals", bool(floored)),
        ("upper_cap_applied", False),
        ("integrated_direction", _direction(delta)),
        ("evidence_family_disposition", evidence_summary),
        ("history_consumption_status", sc["history_consumption_status"]),
        ("frequency_consumption_status", sc["frequency_consumption_status"]),
        ("monthly_consumption_status", sc["monthly_consumption_status"]),
        ("probability_consumption_status", sc["probability_consumption_status"]),
        ("schedule_consumption_status", sc["schedule_consumption_status"]),
        ("pay_app_consumption_status", sc["pay_app_consumption_status"]),
        ("operator_control_status", _operator_status(decision)),
        ("operator_control_id", (decision or {}).get("control_id")),
        ("operator_model_control_status", _operator_model_status(mdecision)),
        ("operator_model_control_id", (mdecision or {}).get("control_id")),
        ("operator_model_value_constraint_policy", (mdecision or {}).get("value_constraint_policy")),
        ("operator_model_type", (mdecision or {}).get("model_type")),
        ("operator_model_controlled_final", money_str(D(mdecision["controlled_final_cost"]))
         if mdecision else None),
        ("dormant_status", (dormant or {}).get("dormant_status")),
        ("dormant_suppression_applied", bool(dormant_suppressed)),
        ("dormant_suppression_reason", (dormant or {}).get("suppression_reason") if dormant_suppressed else None),
        *sb_fields.items(),
        *cb_fields.items(),
        ("reason_codes", sc["reason_codes"]),
    ])
    ha.stamp(forecast_row)

    final_rec = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("accepted_recommended_final_cost", money_str(accepted_final)),
        ("integrated_recommended_final_cost", money_str(integrated_final)),
        ("integrated_cost_to_complete", money_str(integrated_ctc)),
        ("change_amount", money_str(delta)),
        ("history_final_cost_weight", str(w.quantize(Decimal("0.0001")))),
        ("floored_at_actuals", bool(floored)), ("upper_cap_applied", False),
        ("cost_basis_status", cb_decision["cost_basis_status"]),
        ("staffing_basis_status", sb_decision["staffing_basis_status"]),
        ("reason_codes", sc["reason_codes"]),
    ])
    ha.stamp(final_rec)

    floor_audit = OrderedDict([
        ("budget_code_key", key), ("actual_cost_to_date", money_str(actual_floor)),
        ("integrated_recommended_final_cost", money_str(integrated_final)),
        ("floor_respected", bool(integrated_final >= actual_floor)),
        ("upper_cap_applied", False),
    ])
    return forecast_row, final_rec, floor_audit, integrated_final, integrated_ctc, cb_decision, sb_decision


def _operator_status(decision) -> str:
    if not decision:
        return "none"
    if decision.get("dollar_applied"):
        return "applied_dollar"
    if decision.get("timing_applied"):
        return "applied_timing_only"
    return "present"


def _operator_model_status(decision) -> str:
    if not decision:
        return "none"
    if decision.get("changes_deterministic_final"):
        return "applied_model_value"
    return "applied_model_shape_or_window"


def _direction(delta: Decimal) -> str:
    if delta > Decimal("0.01"):
        return "integrated_increase_review"
    if delta < Decimal("-0.01"):
        return "integrated_decrease_review"
    return "hold"
