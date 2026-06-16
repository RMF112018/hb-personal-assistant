"""Assemble a per-budget-code signal bundle from context, v2 analysis, and schedule packages.

All money is carried as Decimal-strings; downstream estimators re-parse with ``dec()``. Float days
and counts are kept as-is (not money). Nothing here mutates source data.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from ..common.dates import normalize_date
from ..common.io import read_jsonl
from ..common.money import D, dec, money_str

DAYS_PER_MONTH = Decimal("30.4375")
BURN_WINDOW = 6  # trailing months used for the burn-rate baseline


def _to_date(s) -> Optional[date]:
    ds = normalize_date(s)
    if not ds:
        return None
    y, m, d = ds.split("-")
    try:
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def months_between(start: Optional[date], end: Optional[date]) -> Optional[Decimal]:
    """Calendar months from start to end (>= 0), Decimal, 2dp. None if either is missing."""
    if not start or not end:
        return None
    days = Decimal((end - start).days)
    if days <= 0:
        return Decimal("0.00")
    return (days / DAYS_PER_MONTH).quantize(Decimal("0.01"))


def _stats(values: list[Decimal]) -> tuple[Optional[str], Optional[str]]:
    """Return (mean_str, coefficient_of_variation_str) over Decimal values, or (None, None)."""
    if not values:
        return None, None
    n = Decimal(len(values))
    mean = sum(values, Decimal("0")) / n
    if mean == 0:
        return money_str(mean), None
    var = sum(((v - mean) ** 2 for v in values), Decimal("0")) / n
    std = var.sqrt()
    cov = (std / mean).copy_abs()
    return money_str(mean), str(cov.quantize(Decimal("0.0001")))


def load_owner_history(context_pkg: Path) -> dict:
    """Group owner pay-app line items by mapped budget key, sorted by period_to (the reliable key).

    Returns ``{budget_code_key: [ {period_to, application_no, percent_complete,
    total_completed_and_stored_to_date, this_period_completed} ... ]}``.
    """
    path = Path(context_pkg) / "canonical" / "owner_pay_app_line_items_mapped.jsonl"
    by_key: dict[str, list] = defaultdict(list)
    if not path.exists():
        return {}
    for r in read_jsonl(path):
        key = r.get("mapped_budget_code_key")
        if not key or r.get("mapping_status") != "mapped":
            continue
        by_key[key].append(OrderedDict([
            ("period_to", r.get("period_to")),
            ("application_no", r.get("application_no")),
            ("percent_complete", r.get("percent_complete")),
            ("total_completed_and_stored_to_date", r.get("total_completed_and_stored_to_date")),
            ("this_period_completed", r.get("this_period_completed")),
        ]))
    for key, rows in by_key.items():
        rows.sort(key=lambda x: normalize_date(x["period_to"]) or "")
    return by_key


def load_cashflow_totals(schedule_pkg: Path) -> dict:
    """Sum the schedule cash-flow allocation per budget key (allocated months only)."""
    path = Path(schedule_pkg) / "schedule_cashflow_timing_curve.jsonl"
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    if not path.exists():
        return {}
    for r in read_jsonl(path):
        if r.get("allocation_method") and r.get("allocation_method") != "not_allocated":
            totals[r["budget_code_key"]] += D(r.get("scheduled_allocation_amount"))
    return {k: money_str(v) for k, v in totals.items()}


def build_signal_bundle(ctx: dict, rec: dict, sched: Optional[dict], owner_hist: list,
                        cashflow_total: Optional[str], data_date: Optional[str],
                        project_finish: Optional[str], project_key: str) -> OrderedDict:
    """One signal bundle row per budget code."""
    amounts = ctx.get("budget_amounts") or {}
    actuals = ctx.get("actuals") or {}
    owner = ctx.get("owner_pay_app") or {}
    procore = ctx.get("procore_subcontractor_pay_apps") or {}
    commitments = ctx.get("commitments") or {}

    monthly = actuals.get("monthly_actuals") or []
    # Burn baseline: completed (through-May) months only; June is partial/leading.
    burn_months = [m for m in monthly if m.get("actual_period_bucket") == "through_may_2026"]
    burn_months.sort(key=lambda m: m.get("month") or "")
    burn_vals = [D(m.get("amount_decimal_string")) for m in burn_months]
    window = burn_vals[-BURN_WINDOW:] if burn_vals else []
    mean_str, cov_str = _stats(window)

    actual_to_date = actuals.get("actual_cost_all_source_to_date")

    # Two independent horizons so burn-rate (global) and schedule-ETC (code-specific) differ.
    dd = _to_date(data_date)
    sched_finish = _to_date(sched.get("latest_remaining_finish")) if sched else None
    remaining_months_schedule = months_between(dd, sched_finish)
    remaining_months_project = months_between(dd, _to_date(project_finish))

    committed = amounts.get("committed_costs")
    invoiced = amounts.get("commitment_invoiced")
    pipeline = None
    if dec(committed) and dec(committed) > 0 and dec(invoiced) is not None:
        pipeline = str((D(invoiced) / D(committed)).quantize(Decimal("0.0001")))

    evidence = sum([
        1 if dec(actual_to_date) and dec(actual_to_date) > 0 else 0,
        1 if owner.get("mapping_status") not in (None, "none") else 0,
        1 if procore.get("mapping_status") not in (None, "none") else 0,
        1 if dec(committed) and dec(committed) > 0 else 0,
        1 if sched and sched.get("schedule_mapping_status") == "mapped" else 0,
    ])

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", ctx.get("budget_code_key")),
        ("sub_job", ctx.get("sub_job")),
        ("cost_code", ctx.get("cost_code")),
        ("category", ctx.get("category")),
        ("budget_code_description", ctx.get("budget_code_description")),
        # accounting actuals (truth)
        ("actual_cost_all_source_to_date", money_str(actual_to_date)),
        ("actual_cost_through_may_2026", money_str(actuals.get("actual_cost_through_may_2026"))),
        ("actual_cost_june_2026_to_date", money_str(actuals.get("actual_cost_june_2026_to_date"))),
        ("actual_entry_count", actuals.get("actual_entry_count")),
        ("latest_actual_accounting_date", actuals.get("latest_actual_accounting_date")),
        # budget amounts
        ("revised_budget", money_str(amounts.get("revised_budget"))),
        ("projected_costs", money_str(amounts.get("projected_costs"))),
        ("estimated_cost_at_completion", money_str(amounts.get("estimated_cost_at_completion"))),
        ("erp_job_to_date_costs", money_str(amounts.get("erp_job_to_date_costs"))),
        ("forecast_to_complete", money_str(amounts.get("forecast_to_complete"))),
        ("committed_costs", money_str(committed)),
        ("commitment_invoiced", money_str(invoiced)),
        ("original_budget_amount", money_str(amounts.get("original_budget_amount"))),
        # burn / volatility
        ("months_of_actuals", len(monthly)),
        ("burn_window_months", len(window)),
        ("avg_monthly_burn", mean_str),
        ("burn_volatility_cov", cov_str),
        ("latest_actual_month", burn_months[-1]["month"] if burn_months else None),
        # owner
        ("owner_mapping_status", owner.get("mapping_status")),
        ("owner_latest_percent_complete", owner.get("latest_percent_complete")),
        ("owner_latest_total_completed_to_date",
         money_str(owner.get("latest_total_completed_and_stored_to_date"))),
        ("owner_latest_balance_to_finish", money_str(owner.get("latest_balance_to_finish"))),
        ("owner_history_points", len(owner_hist)),
        # procore
        ("procore_mapping_status", procore.get("mapping_status")),
        ("procore_latest_total_completed_to_date",
         money_str(procore.get("latest_total_completed_and_stored_to_date_sum"))),
        # commitments
        ("commitment_count", commitments.get("related_commitment_count")),
        ("commitment_pipeline_ratio", pipeline),
        # schedule
        ("schedule_mapping_status", sched.get("schedule_mapping_status") if sched else "none"),
        ("schedule_open_activity_count", sched.get("open_activity_count") if sched else 0),
        ("schedule_remaining_duration_days", sched.get("remaining_duration_days") if sched else None),
        ("schedule_latest_remaining_finish", sched.get("latest_remaining_finish") if sched else None),
        ("schedule_remaining_work_status",
         sched.get("schedule_remaining_work_status") if sched else "no_schedule_evidence"),
        ("schedule_cashflow_alloc_total", cashflow_total),
        ("cashflow_timing_usable", sched.get("cashflow_timing_usable") if sched else False),
        # horizon
        ("data_date", normalize_date(data_date)),
        ("project_scheduled_finish", normalize_date(project_finish)),
        ("remaining_months_schedule",
         str(remaining_months_schedule) if remaining_months_schedule is not None else None),
        ("remaining_months_project",
         str(remaining_months_project) if remaining_months_project is not None else None),
        # provenance / gaps
        ("evidence_depth", evidence),
        ("data_gap_flags", ctx.get("data_gap_flags") or []),
    ])
