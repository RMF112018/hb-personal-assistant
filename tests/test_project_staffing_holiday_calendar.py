"""Deterministic company holiday calendar generation + seed tests (V76)."""

from __future__ import annotations

import sqlite3

from hb_assistant.construction.analytics.staffing_holiday_calendar import (
    DEFAULT_CALENDAR_KEY,
    ensure_default_company_holiday_calendar,
    generate_company_holidays,
)
from hb_assistant.store.forecast_staffing_tables import V76_CREATE_STATEMENTS

# SOW 2.13 known company-calendar observed dates.
_KNOWN_2026 = {
    "new_years_day": "2026-01-01",
    "memorial_day": "2026-05-25",
    "independence_day": "2026-07-03",  # Jul 4 2026 is Saturday -> observed Friday
    "labor_day": "2026-09-07",
    "thanksgiving_day": "2026-11-26",
    "day_after_thanksgiving": "2026-11-27",
    "christmas_eve": "2026-12-24",
    "christmas_day": "2026-12-25",
    "day_after_christmas": "2026-12-28",  # Dec 26 2026 is Saturday -> observed Monday
    "new_years_eve": "2026-12-31",
}


def _by_key(year: int) -> dict[str, dict]:
    return {h["holiday_key"]: h for h in generate_company_holidays() if h["calendar_year"] == year}


def test_full_coverage_count() -> None:
    holidays = generate_company_holidays()
    # 2026-2040 inclusive = 15 years x 10 holidays.
    assert len(holidays) == 150
    years = {h["calendar_year"] for h in holidays}
    assert years == set(range(2026, 2041))
    assert all(len([h for h in holidays if h["calendar_year"] == y]) == 10 for y in years)


def test_known_2026_observed_dates() -> None:
    by_key = _by_key(2026)
    assert set(by_key) == set(_KNOWN_2026)
    for key, observed in _KNOWN_2026.items():
        assert by_key[key]["observed_date"] == observed, key


def test_new_years_2027_actual_date() -> None:
    # Jan 1 2027 is a Friday -> observed on the actual date.
    assert _by_key(2027)["new_years_day"]["observed_date"] == "2027-01-01"


def test_new_years_eve_is_half_day() -> None:
    nye = _by_key(2026)["new_years_eve"]
    assert nye["duration_type"] == "half_day"
    assert nye["staffing_hours_excluded"] == "4.00"
    assert nye["closed_from_time"] == "12:00"
    assert nye["notes"] == "Office closes at noon"


def test_full_day_holidays_exclude_eight_hours() -> None:
    for key, h in _by_key(2026).items():
        if key == "new_years_eve":
            continue
        assert h["duration_type"] == "full_day"
        assert h["staffing_hours_excluded"] == "8.00"
        assert h["closed_from_time"] is None


def test_observed_shift_sunday_rolls_to_monday() -> None:
    # Jul 4 2027 is a Sunday -> observed Monday Jul 5; nominal date stays Jul 4.
    independence_2027 = _by_key(2027)["independence_day"]
    assert independence_2027["holiday_date"] == "2027-07-04"
    assert independence_2027["observed_date"] == "2027-07-05"


def test_ensure_seed_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")
    for stmt in V76_CREATE_STATEMENTS:
        conn.execute(stmt)
    cal_id = ensure_default_company_holiday_calendar(conn, now="2026-06-27T00:00:00+00:00")
    assert cal_id == f"holcal-{DEFAULT_CALENDAR_KEY}"
    first = conn.execute("SELECT COUNT(*) FROM staffing_holiday_calendar_dates").fetchone()[0]
    assert first == 150
    # Re-seed with a different timestamp must not add rows or change existing stamps.
    ensure_default_company_holiday_calendar(conn, now="2030-01-01T00:00:00+00:00")
    rows = conn.execute(
        "SELECT COUNT(*), MIN(created_utc), MAX(created_utc) FROM staffing_holiday_calendar_dates"
    ).fetchone()
    assert rows[0] == 150
    assert rows[1] == rows[2] == "2026-06-27T00:00:00+00:00"
    conn.close()
