"""Deterministic company holiday calendar generation + idempotent seeding (V76, Phase 1).

Pure, wall-clock-free holiday computation for the default company calendar plus an idempotent
seeder the V76 migration calls. Staffing proration (a later phase) excludes these dates from
business-day counts; this module only generates and persists them.

Rules (SOW 2.13):
- Observed-date shift for fixed-date holidays: Saturday -> observe Friday, Sunday -> observe
  Monday, otherwise the actual date.
- Memorial Day = last Monday in May; Labor Day = first Monday in September; Thanksgiving =
  4th Thursday in November; Day after Thanksgiving = the following Friday.
- Day after Christmas is observed on the next business day strictly after the (observed)
  Christmas Day, so a weekend Dec 26 rolls past the Christmas observance (e.g. 2026: Dec 26 is
  Saturday and Christmas is observed Fri Dec 25, so Day after Christmas is observed Mon Dec 28).
- New Year's Eve is a half day (office closes at noon): 4.00 staffing hours excluded.

The seeder uses deterministic IDs and ``INSERT OR IGNORE`` so re-running never changes row
counts or churns the ``created_utc`` / ``updated_utc`` stamps.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

DEFAULT_CALENDAR_KEY = "company_default_2026_2040"
DEFAULT_CALENDAR_NAME = "Company Holiday Calendar"
DEFAULT_CALENDAR_DESCRIPTION = "Default company holiday calendar (2026-2040)."
DEFAULT_YEAR_START = 2026
DEFAULT_YEAR_END = 2040

_FULL_DAY_HOURS = "8.00"
_HALF_DAY_HOURS = "4.00"

_MONDAY = 0
_THURSDAY = 3
_SATURDAY = 5
_SUNDAY = 6


def _observed(d: date) -> date:
    """Saturday -> Friday, Sunday -> Monday, otherwise the actual date."""
    if d.weekday() == _SATURDAY:
        return d - timedelta(days=1)
    if d.weekday() == _SUNDAY:
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth (1-based) ``weekday`` in ``month``."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last ``weekday`` in ``month``."""
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _next_business_day(d: date) -> date:
    """First Mon-Fri strictly after ``d``."""
    nd = d + timedelta(days=1)
    while nd.weekday() >= _SATURDAY:
        nd += timedelta(days=1)
    return nd


def _full(key: str, name: str, nominal: date, observed: date) -> dict[str, Any]:
    return {
        "calendar_year": nominal.year,
        "holiday_key": key,
        "holiday_name": name,
        "holiday_date": nominal.isoformat(),
        "observed_date": observed.isoformat(),
        "duration_type": "full_day",
        "closed_from_time": None,
        "closed_until_time": None,
        "staffing_hours_excluded": _FULL_DAY_HOURS,
        "notes": None,
    }


def _holidays_for_year(year: int) -> list[dict[str, Any]]:
    new_years = date(year, 1, 1)
    memorial = _last_weekday(year, 5, _MONDAY)
    independence = date(year, 7, 4)
    labor = _nth_weekday(year, 9, _MONDAY, 1)
    thanksgiving = _nth_weekday(year, 11, _THURSDAY, 4)
    day_after_thanksgiving = thanksgiving + timedelta(days=1)
    christmas_eve = date(year, 12, 24)
    christmas = date(year, 12, 25)
    christmas_observed = _observed(christmas)
    day_after_christmas_nominal = date(year, 12, 26)
    day_after_christmas_observed = _next_business_day(christmas_observed)
    new_years_eve = date(year, 12, 31)

    holidays = [
        _full("new_years_day", "New Year's Day", new_years, _observed(new_years)),
        _full("memorial_day", "Memorial Day", memorial, memorial),
        _full("independence_day", "Independence Day", independence, _observed(independence)),
        _full("labor_day", "Labor Day", labor, labor),
        _full("thanksgiving_day", "Thanksgiving Day", thanksgiving, thanksgiving),
        _full(
            "day_after_thanksgiving",
            "Day after Thanksgiving",
            day_after_thanksgiving,
            day_after_thanksgiving,
        ),
        _full("christmas_eve", "Christmas Eve", christmas_eve, _observed(christmas_eve)),
        _full("christmas_day", "Christmas Day", christmas, christmas_observed),
        _full(
            "day_after_christmas",
            "Day after Christmas",
            day_after_christmas_nominal,
            day_after_christmas_observed,
        ),
    ]
    holidays.append(
        {
            "calendar_year": year,
            "holiday_key": "new_years_eve",
            "holiday_name": "New Year's Eve",
            "holiday_date": new_years_eve.isoformat(),
            "observed_date": _observed(new_years_eve).isoformat(),
            "duration_type": "half_day",
            "closed_from_time": "12:00",
            "closed_until_time": None,
            "staffing_hours_excluded": _HALF_DAY_HOURS,
            "notes": "Office closes at noon",
        }
    )
    return holidays


def generate_company_holidays(
    year_start: int = DEFAULT_YEAR_START, year_end: int = DEFAULT_YEAR_END
) -> list[dict[str, Any]]:
    """All company holidays for ``year_start``..``year_end`` inclusive (deterministic order)."""
    out: list[dict[str, Any]] = []
    for year in range(year_start, year_end + 1):
        out.extend(_holidays_for_year(year))
    return out


def _calendar_id(calendar_key: str) -> str:
    return f"holcal-{calendar_key}"


def _date_id(holiday_calendar_id: str, calendar_year: int, holiday_key: str) -> str:
    return f"{holiday_calendar_id}-{calendar_year}-{holiday_key}"


def ensure_default_company_holiday_calendar(conn: sqlite3.Connection, *, now: str) -> str:
    """Idempotently seed the default company holiday calendar + its dates. Returns calendar id.

    ``now`` is the migration timestamp (single value per apply). ``INSERT OR IGNORE`` keeps
    re-application from changing row counts or churning stamps.
    """
    cal_id = _calendar_id(DEFAULT_CALENDAR_KEY)
    conn.execute(
        "INSERT OR IGNORE INTO staffing_holiday_calendars "
        "(holiday_calendar_id, calendar_key, calendar_name, description, active_status, "
        "created_utc, updated_utc) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            cal_id,
            DEFAULT_CALENDAR_KEY,
            DEFAULT_CALENDAR_NAME,
            DEFAULT_CALENDAR_DESCRIPTION,
            "active",
            now,
            now,
        ),
    )
    for h in generate_company_holidays():
        conn.execute(
            "INSERT OR IGNORE INTO staffing_holiday_calendar_dates "
            "(holiday_date_id, holiday_calendar_id, calendar_year, holiday_key, holiday_name, "
            "holiday_date, observed_date, duration_type, closed_from_time, closed_until_time, "
            "staffing_hours_excluded, notes, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _date_id(cal_id, h["calendar_year"], h["holiday_key"]),
                cal_id,
                h["calendar_year"],
                h["holiday_key"],
                h["holiday_name"],
                h["holiday_date"],
                h["observed_date"],
                h["duration_type"],
                h["closed_from_time"],
                h["closed_until_time"],
                h["staffing_hours_excluded"],
                h["notes"],
                now,
                now,
            ),
        )
    return cal_id
