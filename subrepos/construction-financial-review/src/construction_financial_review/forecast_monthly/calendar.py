"""Forecast calendar: the remaining forecast months and day-aware partial current month.

Start month = override (``--forecast-start-month YYYY-MM``) else the captured system as-of month.
End month = the month containing the latest scheduled finish date. The current month (when it equals
the system month and is the start month) is PARTIAL: only its unbooked day remainder is forecast,
because the elapsed/booked portion is already in CostEntries actuals and already netted out of CTC.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional


def month_str(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def parse_month(ym: str) -> tuple[int, int]:
    return int(ym[:4]), int(ym[5:7])


def add_months(ym: str, n: int) -> str:
    y, m = parse_month(ym)
    idx = (y * 12 + (m - 1)) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_index(ym: str) -> int:
    y, m = parse_month(ym)
    return y * 12 + (m - 1)


def months_between(start_ym: str, end_ym: str) -> list[str]:
    """Inclusive list of YYYY-MM from start to end (empty if end < start)."""
    out = []
    cur = start_ym
    while month_index(cur) <= month_index(end_ym):
        out.append(cur)
        cur = add_months(cur, 1)
    return out


def days_in_month(ym: str) -> int:
    y, m = parse_month(ym)
    first = date(y, m, 1)
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return (nxt - first).days


def remaining_fraction(as_of: date) -> str:
    """Unbooked day-remainder fraction of the as-of month (today counts as still available)."""
    dim = days_in_month(month_str(as_of))
    rem = dim - as_of.day + 1
    rem = max(0, min(dim, rem))
    return str((Decimal(rem) / Decimal(dim)).quantize(Decimal("0.0001")))


def build_calendar(latest_finish_date: Optional[str], as_of: date,
                   override_start_month: Optional[str] = None) -> OrderedDict:
    """Build the forecast window. ``latest_finish_date`` is YYYY-MM-DD (or None for fallback handling
    by the caller). Returns the month rows + window metadata."""
    system_month = month_str(as_of)
    start_month = override_start_month or system_month
    override_used = override_start_month is not None
    end_month = (latest_finish_date[:7] if latest_finish_date and len(latest_finish_date) >= 7
                 else None)
    if end_month is None or month_index(end_month) < month_index(start_month):
        # Caller records the fallback in data_quality_warnings; default to a single start month.
        end_month = start_month

    months = months_between(start_month, end_month)
    cur_frac = remaining_fraction(as_of)
    rows = []
    for i, ym in enumerate(months):
        is_current = (ym == system_month)
        is_partial = is_current and (ym == start_month)
        rows.append(OrderedDict([
            ("forecast_month", ym),
            ("month_sequence", i + 1),
            ("is_current_month", is_current),
            ("is_partial_current_month", is_partial),
            ("month_remaining_fraction", cur_frac if is_partial else "1.0000"),
        ]))
    return OrderedDict([
        ("forecast_start_month", start_month),
        ("forecast_end_month", end_month),
        ("system_month", system_month),
        ("forecast_as_of_date", as_of.isoformat()),
        ("override_used", override_used),
        ("current_month_remaining_fraction", cur_frac),
        ("month_count", len(months)),
        ("months", rows),
    ])
