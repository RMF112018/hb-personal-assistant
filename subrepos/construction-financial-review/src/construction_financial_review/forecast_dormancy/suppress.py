"""Apply a dormant decision to a forecast recommendation and build the suppression audit row.

Suppression is a trend/inactivity conclusion: it zeroes the remaining forecast and anchors the final to
actual cost to date. It NEVER reduces actual cost to date and NEVER sets the final below actuals.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, money_str

ZERO = Decimal("0")

# overrun flags that must be cleared when a code is suppressed (no future cost => no overrun)
_OVERRUN_FIELDS = ("overrun_projected", "overrun_vs_current_projected_cost", "overrun_vs_revised_budget",
                   "overrun_vs_committed_cost", "overrun_vs_owner_scope_value", "worst_credible_overrun")


def suppress_recommendation(rec: dict, decision: dict) -> "OrderedDict":
    """Return a copy of an intelligence recommendation with future cost zeroed + dormant disclosure.

    Returns (new_rec, before) where ``before`` captures the pre-suppression CTC/final for the audit.
    """
    actual = D(rec.get("actual_cost_all_source_to_date") if rec.get("actual_cost_all_source_to_date")
               is not None else decision.get("actual_cost_to_date"))
    before = OrderedDict([
        ("recommended_cost_to_complete", rec.get("recommended_cost_to_complete")),
        ("recommended_final_cost", rec.get("recommended_final_cost")),
        ("worst_credible_final_cost", rec.get("worst_credible_final_cost")),
    ])
    out = OrderedDict(rec)
    out["recommended_cost_to_complete"] = "0.00"
    out["worst_credible_cost_to_complete"] = "0.00"
    out["recommended_final_cost"] = money_str(actual)
    out["worst_credible_final_cost"] = money_str(actual)
    out["forecast_direction"] = "hold"
    for f in _OVERRUN_FIELDS:
        if f in out and isinstance(out[f], bool):
            out[f] = False
    # recompute variance-to-reference fields off the suppressed final (= actual), if present
    proj = dec(decision.get("projected_cost"))
    rev = dec(decision.get("current_budget"))
    if "recommended_variance_to_current_projected_cost" in out and proj is not None:
        out["recommended_variance_to_current_projected_cost"] = money_str(actual - proj)
    if "recommended_variance_to_revised_budget" in out and rev is not None:
        out["recommended_variance_to_revised_budget"] = money_str(actual - rev)
    out["dormant_status"] = decision["dormant_status"]
    out["dormant_suppression_applied"] = True
    out["dormant_suppression_reason"] = decision["suppression_reason"]
    out["dormant_forecast_basis"] = decision["dormant_status"] + "_zero_remaining"
    out["closure_phrase_detected"] = decision["closure_phrase_detected"]
    return out, before


def audit_row(decision: dict, before: dict) -> "OrderedDict":
    """Per-code dormant suppression audit row (point 7 schema)."""
    before_ctc = before.get("recommended_cost_to_complete")
    after_ctc = "0.00" if decision["suppression_applied"] else before_ctc
    after_final = decision["actual_cost_to_date"] if decision["suppression_applied"] else before.get("recommended_final_cost")
    return OrderedDict([
        ("budget_code_key", decision["budget_code_key"]), ("cost_code", decision["cost_code"]),
        ("category", decision["category"]), ("description", decision["description"]),
        ("dormant_status", decision["dormant_status"]),
        ("closure_phrase_detected", decision["closure_phrase_detected"]),
        ("last_actual_month", decision["last_actual_month"]),
        ("months_since_last_actual", decision["months_since_last_actual"]),
        ("trailing_zero_months", decision["trailing_zero_months"]),
        ("actual_cost_to_date", decision["actual_cost_to_date"]),
        ("current_budget", decision["current_budget"]), ("projected_cost", decision["projected_cost"]),
        ("committed_cost", decision["committed_cost"]),
        ("open_commitment_remaining", decision["open_commitment_remaining"]),
        ("owner_pay_app_recent_activity", decision["owner_pay_app_recent_activity"]),
        ("subcontractor_pay_app_recent_activity", decision["subcontractor_pay_app_recent_activity"]),
        ("schedule_remaining_evidence", decision["schedule_remaining_evidence"]),
        ("operator_control_override", decision["operator_control_override"]),
        ("suppression_applied", decision["suppression_applied"]),
        ("suppression_reason", decision["suppression_reason"]),
        ("recommended_cost_to_complete_before_suppression", before_ctc),
        ("recommended_cost_to_complete_after_suppression", after_ctc),
        ("monthly_forecast_before_suppression", before_ctc),
        ("monthly_forecast_after_suppression", "0.00" if decision["suppression_applied"] else before_ctc),
        ("final_forecast_after_suppression", after_final),
    ])
