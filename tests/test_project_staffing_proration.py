"""Phase 2a holiday business-day proration tests."""

from __future__ import annotations

from decimal import Decimal

from hb_assistant.construction.forecast.staffing.proration import (
    business_day_units,
    holiday_duration_map,
)

# Observed 2026 company holidays relevant to July/September/December windows.
_HOLIDAYS = {
    "2026-07-03": "full_day",  # Independence Day (observed)
    "2026-09-07": "full_day",  # Labor Day
    "2026-12-24": "full_day",  # Christmas Eve
    "2026-12-25": "full_day",  # Christmas Day
    "2026-12-28": "full_day",  # Day after Christmas (observed)
    "2026-12-31": "half_day",  # New Year's Eve (half day)
}


def test_excludes_weekends() -> None:
    # Mon 2026-06-01 .. Sun 2026-06-07 => 5 business days, no holidays.
    units = business_day_units("2026-06-01", "2026-06-07")
    assert units == {"2026-06": Decimal("5")}


def test_excludes_full_day_holiday() -> None:
    # Week containing Labor Day (Mon 2026-09-07): Mon..Fri = 5 weekdays, minus 1 holiday = 4.
    units = business_day_units("2026-09-07", "2026-09-11", holiday_dates=_HOLIDAYS)
    assert units == {"2026-09": Decimal("4")}


def test_half_day_counts_as_half() -> None:
    # Thu 2026-12-31 is a half day; alone it is 0.5 units.
    units = business_day_units("2026-12-31", "2026-12-31", holiday_dates=_HOLIDAYS)
    assert units == {"2026-12": Decimal("0.5")}


def test_multi_month_split() -> None:
    units = business_day_units("2026-06-29", "2026-07-03", holiday_dates=_HOLIDAYS)
    # Jun 29 (Mon), 30 (Tue) = 2; Jul 1 (Wed), 2 (Thu) = 2, Jul 3 holiday = 0.
    assert units == {"2026-06": Decimal("2"), "2026-07": Decimal("2")}


def test_single_weekend_day_is_zero() -> None:
    # Sat 2026-06-06 alone -> month present with 0 units.
    assert business_day_units("2026-06-06", "2026-06-06") == {"2026-06": Decimal("0")}


def test_finish_before_start_is_empty() -> None:
    assert business_day_units("2026-07-10", "2026-07-01") == {}


def test_holiday_duration_map() -> None:
    rows = [
        {"observed_date": "2026-12-25", "duration_type": "full_day"},
        {"observed_date": "2026-12-31", "duration_type": "half_day"},
        {"observed_date": None, "duration_type": "full_day"},
    ]
    assert holiday_duration_map(rows) == {
        "2026-12-25": "full_day",
        "2026-12-31": "half_day",
    }
