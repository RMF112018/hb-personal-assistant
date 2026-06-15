"""Priority 4 — actual-cost lag diagnostics.

Detects whether CostEntries/Sage actuals may lag field/billing/schedule reality, surfacing it as a
confidence / data-gap issue. Compares CostEntries activity (from accepted trend evidence + context
amounts) against leading indicators (subcontractor invoices, owner pay apps, schedule activity). NO
actual cost is ever inferred from invoice / pay-app / schedule data — only a lag-risk flag is raised.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from decimal import Decimal

from ..common.money import D, money_str
from ..forecast_comprehensive import human_acceptance as ha

ZERO = Decimal("0")


def _cfg(cfg):
    return (cfg or {}).get("forecast_improvement_audit") or {}


def build(inputs: dict, cfg: dict):
    """Return (rows, gaps)."""
    fia = _cfg(cfg)
    gap_months = int(fia.get("lag_recency_gap_months", 2))
    zero_threshold = D(fia.get("lag_zero_threshold", "1.0"))
    project_key = inputs["project_key"]

    rows, gaps = [], []
    by_class = Counter()
    for key in sorted(inputs["budget_by_key"]):
        entry = inputs["budget_by_key"][key]
        amt = (entry.get("amounts") or {})
        trend = inputs["trend_by_key"].get(key) or {}
        inv = inputs["latest_sub_invoice_by_key"].get(key) or {}
        sched = inputs["sched_evidence_by_key"].get(key) or {}

        actual = D(amt.get("costentries_total_amount"))
        recency_gap = int(trend.get("recency_gap_months") or 0)
        late_emergence = bool(trend.get("late_cost_emergence"))
        months_actuals = int(trend.get("months_of_completed_actuals") or 0)
        recent_invoice_work = D(inv.get("latest_work_completed_this_period"))
        open_activities = int(sched.get("open_activity_count") or 0)
        sched_active = (sched.get("schedule_remaining_work_status") in ("remaining_work", "active")) \
            or open_activities > 0

        has_indicator = bool(inv) or bool(sched) or months_actuals > 0
        if not has_indicator:
            gaps.append(OrderedDict([
                ("project_key", project_key), ("improvement", "priority_4_actual_cost_lag"),
                ("budget_code_key", key), ("gap_type", "insufficient_lag_evidence"),
                ("detail", "no trend / invoice / schedule indicators for this code")]))
            continue

        flags = []
        stale_actuals = actual.copy_abs() <= zero_threshold or recency_gap >= gap_months
        if recent_invoice_work > zero_threshold and stale_actuals:
            flags.append("invoice_ahead_of_costentries")
        if sched_active and actual.copy_abs() <= zero_threshold:
            flags.append("schedule_active_no_actuals")
        if late_emergence:
            flags.append("recent_actuals_emerged_after_inactivity")

        lag_risk = bool(flags)
        classification = "lag_risk" if lag_risk else (
            "insufficient_data" if months_actuals == 0 and not flags else "no_lag")
        by_class[classification] += 1
        # only emit rows that carry a signal (lag risk) or an explicit no-lag where actuals are current
        if not lag_risk and classification == "no_lag" and recency_gap < gap_months:
            continue
        row = OrderedDict([
            ("project_key", project_key), ("budget_code_key", key), ("cost_code", entry.get("cost_code")),
            ("lag_classification", classification), ("lag_risk", lag_risk),
            ("lag_flags", flags),
            ("actual_cost_to_date", money_str(actual) or "0.00"),
            ("recency_gap_months", recency_gap),
            ("months_of_completed_actuals", months_actuals),
            ("recent_subcontractor_invoice_work", money_str(recent_invoice_work)),
            ("latest_subcontractor_billing_date", inv.get("latest_billing_date")),
            ("schedule_open_activity_count", open_activities),
            ("schedule_remaining_work_status", sched.get("schedule_remaining_work_status")),
            ("actual_cost_inferred_from_indicators", False),
            ("note", "lag-risk flag only; no actual cost is inferred from invoice/pay-app/schedule data"),
        ])
        rows.append(ha.stamp(row))
    rows.sort(key=lambda r: (r["lag_classification"], r["budget_code_key"]))
    summary_gap = OrderedDict([
        ("project_key", project_key), ("improvement", "priority_4_actual_cost_lag"),
        ("gap_type", "lag_classification_census"),
        ("detail", dict(by_class))])
    gaps.append(summary_gap)
    return rows, gaps
