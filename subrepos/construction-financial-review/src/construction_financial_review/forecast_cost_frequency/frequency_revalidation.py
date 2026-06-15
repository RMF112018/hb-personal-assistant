"""Revalidate documented/observed cadence against the MOST RECENT actuals before each fresh run.

If a code previously read monthly but the most recent ``cadence_change_recent_months`` now show multiple
entries per month (or vice-versa, or activity stopped), a cadence change is surfaced and the advisory
effective class is updated. For configured staffing codes the weekly override still wins as the
effective cadence, but a contradicting recent pattern is still reported (so a human can review).
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from .weekday_calendar import month_index

ZERO = Decimal("0")

# coarse cadence rank for comparing recent vs overall (higher = more frequent)
_RANK = {
    "insufficient_evidence": 0, "inactive_or_complete": 0, "one_time_or_milestone": 1,
    "monthly_observed": 2, "twice_monthly_observed": 3, "weekly_observed": 4,
    "weekly_internal_staffing": 4, "irregular": 2,
}


def _avg_class(avg: Decimal, cfg_fcf: dict) -> str:
    weekly = Decimal(str(cfg_fcf.get("weekly_entry_count_threshold", 4)))
    bimonthly = Decimal(str(cfg_fcf.get("bi_monthly_entry_count_threshold", 2)))
    monthly = Decimal(str(cfg_fcf.get("monthly_frequency_entry_count_threshold", 1)))
    if avg >= weekly:
        return "weekly_observed"
    if avg >= bimonthly:
        return "twice_monthly_observed"
    if avg >= monthly:
        return "monthly_observed"
    return "one_time_or_milestone"


def revalidate(detected: OrderedDict, cfg_fcf: dict, complete_boundary: str,
               is_staffing: bool, project_key: str, key: str, cost_code: str) -> OrderedDict:
    recent_window = int(cfg_fcf.get("cadence_change_recent_months", 3))
    observed = detected["observed_frequency_class"]
    ecbm = detected.get("entry_count_by_month") or {}

    cutoff = month_index(complete_boundary) - (recent_window - 1)
    recent_counts = [c for m, c in ecbm.items() if month_index(m) >= cutoff]
    recent_avg = (sum((Decimal(c) for c in recent_counts), ZERO) / Decimal(len(recent_counts))
                  ) if recent_counts else ZERO
    recent_class = _avg_class(recent_avg, cfg_fcf) if recent_counts else "inactive_or_complete"

    change = False
    basis = "recent pattern consistent with observed cadence"
    if recent_counts:
        if _RANK.get(recent_class, 2) > _RANK.get(observed, 2):
            change = True
            basis = (f"recent {recent_window}mo cadence ({recent_class}, avg "
                     f"{recent_avg.quantize(Decimal('0.01'))} entries/mo) is more frequent than the "
                     f"overall observed cadence ({observed})")
        elif _RANK.get(recent_class, 2) < _RANK.get(observed, 2):
            change = True
            basis = (f"recent {recent_window}mo cadence ({recent_class}, avg "
                     f"{recent_avg.quantize(Decimal('0.01'))} entries/mo) is less frequent than the "
                     f"overall observed cadence ({observed})")
    elif observed not in ("inactive_or_complete", "insufficient_evidence"):
        change = True
        basis = f"no actuals in the recent {recent_window}mo window though overall cadence was {observed}"

    # configured staffing override is authoritative for the effective class; otherwise apply the change
    if is_staffing:
        revalidated_effective = "weekly_internal_staffing"
    else:
        revalidated_effective = recent_class if change else observed

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", cost_code),
        ("is_internal_staffing_code", is_staffing),
        ("documented_observed_frequency_class", observed),
        ("recent_window_months", recent_window),
        ("recent_avg_entries_per_month", str(recent_avg.quantize(Decimal("0.0001")))),
        ("recent_frequency_class", recent_class),
        ("cadence_change_detected", change),
        ("cadence_change_basis", basis),
        ("revalidated_effective_frequency_class", revalidated_effective),
        ("requires_human_acceptance", True),
    ])
