"""Classify cost-incurrence cadence per budget code from real CostEntries.

Evidence is per-month entry counts (number of cost entries booked that month) plus, when available,
transaction-level accounting dates for intra-month spacing. CostEntries are accounting truth; this only
reads them. Partial/incomplete current month (after the latest-complete boundary) is excluded from
cadence detection. Graceful degradation: when only monthly aggregates exist (no transaction dates),
weekly is never inferred for non-staffing codes — classification is capped at monthly/irregular/inactive
with lower confidence.

Classes: weekly_internal_staffing (staffing override, set by caller), weekly_observed,
twice_monthly_observed, monthly_observed, irregular, one_time_or_milestone, inactive_or_complete,
insufficient_evidence.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D
from .weekday_calendar import month_index

ZERO = Decimal("0")


def _q4(x) -> str:
    return str(Decimal(x).quantize(Decimal("0.0001")))


def _active_months(monthly_actuals: list, complete_boundary: str) -> list:
    """(month, entry_count, amount) for months <= boundary with at least one entry, sorted by month."""
    out = []
    for ma in monthly_actuals or []:
        m = ma.get("month")
        if not m or month_index(m) > month_index(complete_boundary):
            continue
        ec = int(ma.get("entry_count") or 0)
        amt = D(ma.get("amount_decimal_string"))
        if ec > 0:
            out.append((m, ec, amt))
    out.sort(key=lambda t: month_index(t[0]))
    return out


def _dispersion(counts: list) -> Decimal:
    """Coefficient of variation of monthly entry counts (0 = perfectly even)."""
    if not counts:
        return ZERO
    n = Decimal(len(counts))
    mean = sum((Decimal(c) for c in counts), ZERO) / n
    if mean == 0:
        return ZERO
    var = sum(((Decimal(c) - mean) ** 2 for c in counts), ZERO) / n
    return (var.sqrt() / mean)


def classify(monthly_actuals: list, txn_dates: list, complete_boundary: str,
             cfg_fcf: dict, is_staffing: bool) -> OrderedDict:
    minimum_months = int(cfg_fcf.get("minimum_months_for_observed_frequency", 3))
    monthly_thr = Decimal(str(cfg_fcf.get("monthly_frequency_entry_count_threshold", 1)))
    bimonthly_thr = Decimal(str(cfg_fcf.get("bi_monthly_entry_count_threshold", 2)))
    weekly_thr = Decimal(str(cfg_fcf.get("weekly_entry_count_threshold", 4)))
    recent_window = int(cfg_fcf.get("cadence_change_recent_months", 3))

    active = _active_months(monthly_actuals, complete_boundary)
    months_observed = len(active)
    total_entries = sum(ec for _, ec, _ in active)
    txn_available = bool(txn_dates)
    aggregate_fallback = (months_observed > 0) and not txn_available

    entry_count_by_month = OrderedDict((m, ec) for m, ec, _ in active)
    counts = [ec for _, ec, _ in active]
    dispersion = _dispersion(counts)
    avg = (Decimal(total_entries) / Decimal(months_observed)) if months_observed else ZERO

    # recency window relative to the complete boundary
    cutoff = month_index(complete_boundary) - (recent_window - 1)
    recent = [(m, ec) for m, ec, _ in active if month_index(m) >= cutoff]
    recent_months_observed = len(recent)
    latest_active = active[-1][0] if active else None
    staleness = (month_index(complete_boundary) - month_index(latest_active)) if latest_active else None

    def result(cls, source, confidence):
        return OrderedDict([
            ("observed_frequency_class", cls),
            ("cadence_source", source),
            ("frequency_confidence", confidence),
            ("months_observed", months_observed),
            ("recent_months_observed", recent_months_observed),
            ("total_entries", total_entries),
            ("avg_entries_per_active_month", _q4(avg)),
            ("entry_count_dispersion", _q4(dispersion)),
            ("latest_active_month", latest_active),
            ("inactive_months_to_boundary", staleness),
            ("entry_count_by_month", entry_count_by_month),
            ("transaction_level_costentries_available", txn_available),
            ("monthly_aggregate_fallback_used", aggregate_fallback),
        ])

    if months_observed == 0:
        return result("insufficient_evidence", "inferred", "none")

    # genuinely stale -> inactive/complete (no recent activity for > 2x the recency window)
    if staleness is not None and staleness > 2 * recent_window:
        return result("inactive_or_complete", "inferred", "medium" if months_observed >= 3 else "low")

    # very sparse, lumpy spend -> one-time / milestone
    if total_entries <= 2 and months_observed <= 2:
        return result("one_time_or_milestone", "observed" if txn_available else "inferred", "low")

    if months_observed < minimum_months:
        return result("insufficient_evidence", "inferred", "low")

    # entry-count cadence. Without transaction dates AND non-staffing, never infer sub-monthly.
    if aggregate_fallback and not is_staffing:
        if dispersion >= Decimal("1.0"):
            return result("irregular", "inferred", "low")
        return result("monthly_observed", "inferred", "low")

    conf = "high" if (months_observed >= 6 and dispersion < Decimal("0.75")) else "medium"
    if dispersion >= Decimal("1.25") and avg < weekly_thr:
        return result("irregular", "observed", "low")
    if avg >= weekly_thr:
        return result("weekly_observed", "observed", conf)
    if avg >= bimonthly_thr:
        return result("twice_monthly_observed", "observed", conf)
    if avg >= monthly_thr:
        return result("monthly_observed", "observed", conf)
    return result("irregular", "observed", "low")


def observation_row(project_key: str, key: str, cost_code: str, category: str,
                    detected: OrderedDict) -> OrderedDict:
    """Reviewer-facing per-code cadence observation (mirrors the detection evidence)."""
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", cost_code),
        ("category", category),
        ("observed_frequency_class", detected["observed_frequency_class"]),
        ("months_observed", detected["months_observed"]),
        ("recent_months_observed", detected["recent_months_observed"]),
        ("total_entries", detected["total_entries"]),
        ("avg_entries_per_active_month", detected["avg_entries_per_active_month"]),
        ("entry_count_dispersion", detected["entry_count_dispersion"]),
        ("latest_active_month", detected["latest_active_month"]),
        ("entry_count_by_month", detected["entry_count_by_month"]),
        ("transaction_level_costentries_available",
         detected["transaction_level_costentries_available"]),
        ("monthly_aggregate_fallback_used", detected["monthly_aggregate_fallback_used"]),
    ])
