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
from . import human_acceptance as ha

ZERO, ONE = Decimal("0"), Decimal("1")


def build(project_key, key, entry, sc) -> tuple:
    """Return (forecast_row, final_cost_rec, floor_audit_row)."""
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
    delta = integrated_final - accepted_final

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
        ("reason_codes", sc["reason_codes"]),
    ])
    ha.stamp(final_rec)

    floor_audit = OrderedDict([
        ("budget_code_key", key), ("actual_cost_to_date", money_str(actual_floor)),
        ("integrated_recommended_final_cost", money_str(integrated_final)),
        ("floor_respected", bool(integrated_final >= actual_floor)),
        ("upper_cap_applied", False),
    ])
    return forecast_row, final_rec, floor_audit, integrated_final, integrated_ctc


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
