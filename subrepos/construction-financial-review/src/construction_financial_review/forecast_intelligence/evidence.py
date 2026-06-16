"""Assemble one enriched evidence bundle per budget code.

Wraps the proven ``forecast_accuracy.signals.build_signal_bundle`` (used verbatim as the base layer)
and merges the additional families the uncapped estimators need: ERP pending/approved change-order
fields, the owner SOV value, the Procore scheduled value, the recent-trend block, and the schedule
association block. Pure assembly — no forecasting decision is made here.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from ..common.money import money_str
from ..forecast_accuracy import signals


def assemble_evidence(ctx: dict, rec: dict, sched_rollup: Optional[dict], owner_hist: list,
                      cashflow_total: Optional[str], assoc: dict, trend: dict,
                      data_date: Optional[str], project_finish: Optional[str],
                      project_key: str) -> OrderedDict:
    """Return the merged evidence bundle for one budget code."""
    base = signals.build_signal_bundle(ctx, rec, sched_rollup, owner_hist, cashflow_total,
                                       data_date, project_finish, project_key)
    amounts = ctx.get("budget_amounts") or {}
    owner = ctx.get("owner_pay_app") or {}
    procore = ctx.get("procore_subcontractor_pay_apps") or {}

    bundle = OrderedDict(base)
    # ERP per-code extras (references only; never used as a cap).
    bundle["current_projected_cost"] = base.get("projected_costs")
    bundle["pending_cost_changes"] = money_str(amounts.get("pending_cost_changes"))
    bundle["approved_change_orders"] = money_str(amounts.get("approved_cos"))
    # Owner SOV value (the owner's scheduled value at this budget code, when mapped).
    bundle["owner_sov_value"] = money_str(owner.get("latest_current_value"))
    # Procore scheduled value (subcontract SOV) for the progress estimator.
    bundle["procore_scheduled_value"] = money_str(procore.get("latest_scheduled_value_sum"))

    # Recent-trend block.
    bundle["recent_avg_monthly_burn"] = trend.get("recent_avg_monthly_burn")
    bundle["burn_acceleration_ratio"] = trend.get("burn_acceleration_ratio")
    bundle["burn_acceleration_class"] = trend.get("burn_acceleration_class")
    bundle["cost_volatility_cov"] = trend.get("cost_volatility_cov")
    bundle["months_of_completed_actuals"] = trend.get("months_of_completed_actuals")
    bundle["trend_signal"] = trend.get("trend_signal")
    bundle["late_cost_emergence"] = trend.get("late_cost_emergence")
    bundle["credits_deductive_pattern"] = trend.get("credits_deductive_pattern")

    # Schedule association block.
    bundle["schedule_association"] = assoc.get("schedule_association")
    bundle["schedule_confidence"] = assoc.get("schedule_confidence")
    bundle["schedule_influences_estimate"] = assoc.get("influences_code_estimate")
    bundle["assoc_remaining_duration_days"] = assoc.get("remaining_duration_days")
    bundle["assoc_latest_schedule_finish"] = assoc.get("latest_schedule_finish")

    # Richer evidence-family count for confidence.
    families = []
    if _pos(base.get("actual_cost_all_source_to_date")):
        families.append("actuals")
    if base.get("owner_mapping_status") not in (None, "none"):
        families.append("owner_progress")
    if base.get("procore_mapping_status") not in (None, "none"):
        families.append("procore_progress")
    if _pos(base.get("committed_costs")):
        families.append("commitment")
    if assoc.get("schedule_association") in ("direct", "cost_code_family", "owner_scope",
                                             "division", "vendor_or_commitment"):
        families.append("schedule")
    if (trend.get("months_of_completed_actuals") or 0) >= 3:
        families.append("trend")
    bundle["evidence_families_present"] = families
    bundle["evidence_depth_intel"] = len(families)
    return bundle


def _pos(v) -> bool:
    from ..common.money import dec
    d = dec(v)
    return d is not None and d > 0
