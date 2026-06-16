"""Weekday (Mon-Fri) counts per forecast month. Holiday-neutral, fully deterministic.

Lower-level than forecast_monthly: month helpers are inlined here so the cadence slice never imports
forecast_monthly (the dependency is one-way — forecast_monthly imports this slice, never the reverse).
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")


def parse_month(ym: str) -> tuple[int, int]:
    return int(ym[:4]), int(ym[5:7])


def add_months(ym: str, n: int) -> str:
    y, m = parse_month(ym)
    idx = (y * 12 + (m - 1)) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_index(ym: str) -> int:
    y, m = parse_month(ym)
    return y * 12 + (m - 1)


def months_between(start_ym: str, end_ym: str) -> list:
    """Inclusive YYYY-MM list from start to end (empty if end < start)."""
    out, cur = [], start_ym
    while month_index(cur) <= month_index(end_ym):
        out.append(cur)
        cur = add_months(cur, 1)
    return out


def days_in_month(ym: str) -> int:
    y, m = parse_month(ym)
    first = date(y, m, 1)
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return (nxt - first).days


def weekdays_in_month(ym: str) -> int:
    """Count of Monday-Friday days in the month (holiday-neutral)."""
    y, m = parse_month(ym)
    return sum(1 for d in range(1, days_in_month(ym) + 1) if date(y, m, d).weekday() < 5)


def weekday_weight_vector(months: list) -> "OrderedDict[str, Decimal]":
    """Normalized weekday-share weight vector over the forecast months (sums to 1)."""
    counts = OrderedDict((m, Decimal(weekdays_in_month(m))) for m in months)
    total = sum(counts.values(), ZERO)
    if total <= 0:
        n = Decimal(len(months) or 1)
        return OrderedDict((m, ONE / n) for m in months)
    return OrderedDict((m, counts[m] / total) for m in months)


def calendar_rows(months: list, project_key: str) -> list:
    rows = []
    for m in months:
        rows.append(OrderedDict([
            ("project_key", project_key),
            ("forecast_month", m),
            ("calendar_days", days_in_month(m)),
            ("weekday_count", weekdays_in_month(m)),
        ]))
    return rows
