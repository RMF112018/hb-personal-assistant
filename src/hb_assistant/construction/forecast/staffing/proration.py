"""Holiday-aware business-day proration (Phase 2a).

Pure, wall-clock-free counting of eligible business-day units per calendar month between two
inclusive ISO dates. Weekends and full-day holidays count 0; a half-day holiday counts 0.5
(SOW 2.7 / 2.13). Converting day-units to cost (rate x hours basis) is Phase 6 — this layer only
counts days.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable

_FULL_UNIT = Decimal("1")
_HALF_UNIT = Decimal("0.5")
_ZERO = Decimal("0")
_SATURDAY = 5


def holiday_duration_map(date_rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Build ``{observed_date: duration_type}`` from HolidayCalendarRepository.get_dates rows."""
    return {
        row["observed_date"]: row.get("duration_type", "full_day")
        for row in date_rows
        if row.get("observed_date")
    }


def _unit_for(day: date, holiday_dates: dict[str, str]) -> Decimal:
    if day.weekday() >= _SATURDAY:
        return _ZERO
    duration = holiday_dates.get(day.isoformat())
    if duration is None:
        return _FULL_UNIT
    if duration == "half_day":
        return _HALF_UNIT
    return _ZERO  # full_day (or any non-half) holiday


def business_day_units(
    start_date: str,
    finish_date: str,
    *,
    holiday_dates: dict[str, str] | None = None,
) -> dict[str, Decimal]:
    """Eligible business-day units per ``YYYY-MM`` over [start, finish] inclusive.

    Every month the range spans appears in the result (value may be 0 if fully weekend/holiday).
    Returns an empty dict when ``finish`` precedes ``start``.
    """
    start = date.fromisoformat(start_date)
    finish = date.fromisoformat(finish_date)
    if finish < start:
        return {}
    holidays = holiday_dates or {}
    units: dict[str, Decimal] = {}
    day = start
    while day <= finish:
        month = f"{day.year:04d}-{day.month:02d}"
        units[month] = units.get(month, _ZERO) + _unit_for(day, holidays)
        day += timedelta(days=1)
    return units
