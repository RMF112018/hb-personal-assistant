"""Schedule integration onto the crosswalk-v2 forecast recommendations (Phases 6, 9).

Schedule evidence may strengthen review flags, block unsafe decreases, and surface
remaining-exposure / forecast-exhaustion risk. It may NEVER, by itself: set
``recommended_projected_cost``, create a numeric increase, create a new decrease, override
accounting actuals, or override owner/Procore evidence.

Approved refinement: forecast exhaustion uses the deterministic threshold
``actual_cost_all_source_to_date >= 0.90 * current_projected_cost`` (no vague "near projected").
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, materiality, money_str
from . import schedule_rollup

EXHAUSTION_RATIO = Decimal("0.90")   # actuals >= 90% of projected => forecast exhaustion
OWNER_COMPLETE_PCT = Decimal("0.99")

# schedule_forecast_implication values
IMPL_NONE = "none"
IMPL_SUPPORTS_HOLD = "supports_hold"
IMPL_BLOCKS_DECREASE = "blocks_decrease"
IMPL_STRENGTHENS_REVIEW = "strengthens_review_required"
IMPL_REMAINING_EXPOSURE = "supports_remaining_exposure_review"
IMPL_CASHFLOW = "supports_cashflow_timing"
IMPL_MAPPING_REVIEW = "mapping_review_required"


def actuals_near_projected(actual, projected) -> bool:
    """True iff actual >= 0.90 * projected and projected > 0 (deterministic exhaustion test)."""
    a = D(actual)
    p = D(projected)
    if p <= 0:
        return False
    return a >= (EXHAUSTION_RATIO * p)


def _material(rollup: dict) -> bool:
    return rollup.get("schedule_remaining_work_status") == schedule_rollup.RW_MATERIAL


def _neg_float(rollup: dict) -> bool:
    return (rollup.get("negative_float_activity_count") or 0) > 0


def _ambiguous(rollup: dict) -> bool:
    return rollup.get("schedule_mapping_status") == "ambiguous"


def _notch_down(conf: Optional[str]) -> str:
    order = ["none", "low", "medium", "high"]
    if conf not in order:
        return conf or "none"
    i = order.index(conf)
    return order[max(0, i - 1)]


def integrate_recommendation(rec: dict, rollup: dict) -> dict:
    """Apply the schedule integration action rules to one v2 recommendation row (Phase 9).

    Returns a new row preserving every original field and adding ``schedule_*`` fields.
    """
    base_action = rec.get("forecast_action")
    projected = rec.get("current_projected_cost")
    actual = rec.get("actual_cost_all_source_to_date")
    material = _material(rollup)
    neg_float = _neg_float(rollup)
    ambiguous = _ambiguous(rollup)
    exhaustion = material and actuals_near_projected(actual, projected)

    # Defaults: schedule never raises a number; carry the v2 recommendation forward unchanged.
    action = base_action
    rec_projected = rec.get("recommended_projected_cost")
    rec_adjust = rec.get("recommended_forecast_adjustment")
    flags: list[str] = []
    implication = IMPL_NONE
    conf_before = rec.get("confidence")
    conf_after = conf_before
    notes_parts: list[str] = []

    if base_action == "increase_forecast":
        # Preserve the floor-to-actuals increase and its numbers exactly.
        if material:
            flags += ["remaining_schedule_exposure", "schedule_open_work_after_underforecast",
                      "remaining_exposure_review_required"]
            implication = IMPL_REMAINING_EXPOSURE
            notes_parts.append("Underforecast increase preserved; schedule shows material remaining "
                               "work — review remaining exposure above floored actuals.")
        else:
            notes_parts.append("Underforecast increase preserved; no material remaining schedule work.")

    elif base_action == "decrease_forecast":
        if material:
            action = "review_required"
            rec_projected = None
            rec_adjust = None
            flags.append("schedule_blocks_decrease")
            if neg_float:
                flags.append("schedule_negative_float_remaining_work")
            implication = IMPL_BLOCKS_DECREASE
            conf_after = _notch_down(conf_before)
            notes_parts.append("Schedule shows material remaining work; automatic decrease blocked and "
                               "downgraded to review_required (numbers cleared).")
        else:
            notes_parts.append("Decrease retained; no material remaining schedule work to block it.")

    elif base_action == "hold_current_forecast":
        if exhaustion:
            action = "review_required"
            flags.append("schedule_open_work_with_forecast_exhaustion")
            if neg_float:
                flags.append("schedule_negative_float_remaining_work")
            implication = IMPL_STRENGTHENS_REVIEW
            conf_after = _notch_down(conf_before)
            notes_parts.append("Actuals >= 90% of projected with material remaining schedule work; "
                               "hold upgraded to review_required (forecast exhaustion risk).")
        elif material:
            flags.append("schedule_remaining_work_monitor")
            implication = IMPL_SUPPORTS_HOLD
            notes_parts.append("Hold preserved; material remaining schedule work — monitor remaining exposure.")
        else:
            implication = IMPL_SUPPORTS_HOLD if rollup.get("open_activity_count") else IMPL_NONE
            if rollup.get("open_activity_count"):
                flags.append("schedule_remaining_work_supported_hold")

    elif base_action == "review_required":
        if material:
            flags.append("schedule_remaining_work_strengthens_review")
            if neg_float:
                flags.append("schedule_negative_float_remaining_work")
            implication = IMPL_STRENGTHENS_REVIEW
            notes_parts.append("Existing review_required strengthened by material remaining schedule work.")
        else:
            notes_parts.append("Existing review_required preserved.")

    else:
        # insufficient_evidence / mapping_required / anything else: never promote on schedule alone.
        if material:
            flags.append("schedule_open_work_unmapped_or_insufficient_financial_evidence")
            notes_parts.append("Schedule shows remaining work but financial evidence is insufficient; "
                               "action not promoted on schedule alone.")

    # Forecast-exhaustion is an evidence flag regardless of base action (kept consistent across the
    # package); only the hold path changes the action on exhaustion.
    if exhaustion and "schedule_open_work_with_forecast_exhaustion" not in flags:
        flags.append("schedule_open_work_with_forecast_exhaustion")

    if ambiguous:
        flags.append("schedule_mapping_ambiguous")
        if implication == IMPL_NONE:
            implication = IMPL_MAPPING_REVIEW
        notes_parts.append("Schedule cost code maps to multiple canonical categories; "
                           "no single budget_code_key assigned.")

    # Cost-to-complete recomputed only from the (unchanged-or-cleared) recommended projected cost.
    if rec_projected is not None:
        ctc = D(rec_projected) - D(actual)
        ctc = ctc if ctc > 0 else Decimal("0")
        schedule_ctc = money_str(ctc)
    else:
        schedule_ctc = None

    conf_mod = "lowered_due_to_open_schedule_work" if conf_after != conf_before else "unchanged"

    out = OrderedDict(rec)  # preserve all original v2 fields
    out["schedule_mapping_status"] = rollup.get("schedule_mapping_status")
    out["schedule_mapping_confidence"] = rollup.get("schedule_mapping_confidence")
    out["schedule_remaining_work_status"] = rollup.get("schedule_remaining_work_status")
    out["schedule_open_activity_count"] = rollup.get("open_activity_count")
    out["schedule_remaining_duration_days"] = rollup.get("remaining_duration_days")
    out["schedule_negative_float_activity_count"] = rollup.get("negative_float_activity_count")
    out["schedule_risk_flags"] = sorted(set(flags + (rollup.get("schedule_risk_flags") or [])))
    out["schedule_forecast_implication"] = implication
    out["schedule_integrated_forecast_action"] = action
    out["schedule_integrated_recommended_projected_cost"] = rec_projected
    out["schedule_integrated_recommended_forecast_adjustment"] = rec_adjust
    out["schedule_integrated_cost_to_complete"] = schedule_ctc
    out["confidence_before_schedule"] = conf_before
    out["confidence_after_schedule"] = conf_after
    out["schedule_confidence_modifier"] = conf_mod
    out["action_changed_by_schedule"] = action != base_action
    out["schedule_review_notes"] = " ".join(notes_parts) if notes_parts else None
    return out


def build_alignment_row(rec: dict, rollup: dict, ctx: Optional[dict], project_key: str) -> dict:
    """One schedule/forecast alignment row per budget key (Phase 6)."""
    owner = (ctx or {}).get("owner_pay_app") or {}
    procore = (ctx or {}).get("procore_subcontractor_pay_apps") or {}
    projected = rec.get("current_projected_cost")
    actual = rec.get("actual_cost_all_source_to_date")
    material = _material(rollup)
    neg_float = _neg_float(rollup)
    ambiguous = _ambiguous(rollup)
    exhaustion = material and actuals_near_projected(actual, projected)

    owner_pct = dec(owner.get("latest_percent_complete"))
    owner_complete = owner_pct is not None and owner_pct >= OWNER_COMPLETE_PCT
    procore_completed = dec(procore.get("latest_total_completed_and_stored_to_date_sum"))
    open_count = rollup.get("open_activity_count") or 0

    flags = []
    if owner_complete and material:
        flags.append("owner_complete_but_schedule_open")
    if procore_completed is not None and procore_completed > 0 and material:
        flags.append("procore_complete_but_schedule_open")
    if exhaustion:
        flags.append("actuals_high_but_schedule_open")
        flags.append("schedule_open_work_with_forecast_exhaustion")
    if material and owner.get("mapping_status") in (None, "none") and procore.get("mapping_status") in (None, "none"):
        flags.append("schedule_open_work_with_no_payapp_evidence")
    if rollup.get("schedule_remaining_work_status") == schedule_rollup.RW_COMPLETE:
        gap, pct, is_mat = materiality(actual, projected)
        if D(actual) < D(projected) and is_mat:
            flags.append("schedule_complete_but_costs_trailing")
    if ambiguous:
        flags.append("schedule_mapping_ambiguous")
    if neg_float:
        flags.append("schedule_negative_float_remaining_work")
        if material:
            flags.append("schedule_critical_remaining_work")
    if rollup.get("cashflow_timing_usable") and D(projected) - D(actual) > 0:
        flags.append("schedule_cashflow_timing_available")
    if rollup.get("schedule_mapping_status") == "none" and rollup.get("mapped_activity_count", 0) == 0 \
            and rollup.get("ambiguous_candidate_activity_count", 0) == 0:
        flags.append("schedule_no_evidence")

    # implication mirrors the integrated recommendation logic
    integ = integrate_recommendation(rec, rollup)

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", rec.get("budget_code_key")),
        ("budget_amount", rec.get("budget_amount")),
        ("current_projected_cost", projected),
        ("actual_cost_all_source_to_date", actual),
        ("actual_cost_through_may_2026", rec.get("actual_cost_through_may_2026")),
        ("actual_cost_june_2026_to_date", rec.get("actual_cost_june_2026_to_date")),
        ("owner_latest_completed_to_date", owner.get("latest_total_completed_and_stored_to_date")),
        ("owner_latest_percent_complete", owner.get("latest_percent_complete")),
        ("owner_latest_balance_to_finish", owner.get("latest_balance_to_finish")),
        ("procore_latest_completed_to_date", procore.get("latest_total_completed_and_stored_to_date_sum")),
        ("procore_latest_claimed_amount", procore.get("latest_subcontractor_claimed_amount_sum")),
        ("procore_latest_retainage", procore.get("latest_retainage_held_sum")),
        ("existing_forecast_action", rec.get("forecast_action")),
        ("existing_recommended_projected_cost", rec.get("recommended_projected_cost")),
        ("existing_recommended_forecast_adjustment", rec.get("recommended_forecast_adjustment")),
        ("schedule_remaining_work_status", rollup.get("schedule_remaining_work_status")),
        ("schedule_open_activity_count", open_count),
        ("schedule_remaining_duration_days", rollup.get("remaining_duration_days")),
        ("schedule_minimum_total_float_days", rollup.get("minimum_total_float_days")),
        ("schedule_negative_float_activity_count", rollup.get("negative_float_activity_count")),
        ("schedule_alignment_flags", sorted(set(flags))),
        ("schedule_forecast_implication", integ["schedule_forecast_implication"]),
        ("recommended_schedule_integrated_action", integ["schedule_integrated_forecast_action"]),
        ("recommended_schedule_integrated_projected_cost", integ["schedule_integrated_recommended_projected_cost"]),
        ("recommended_schedule_integrated_adjustment", integ["schedule_integrated_recommended_forecast_adjustment"]),
        ("schedule_adjustment_reason", integ["schedule_review_notes"]),
        ("confidence_before_schedule", integ["confidence_before_schedule"]),
        ("confidence_after_schedule", integ["confidence_after_schedule"]),
        ("notes", None),
    ])
