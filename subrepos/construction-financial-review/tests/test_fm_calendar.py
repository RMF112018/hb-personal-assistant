"""Forecast calendar: window start/end, day-aware partial current month, override."""
from datetime import date

from construction_financial_review.forecast_monthly import calendar as cal


def test_default_window_from_system_month():
    c = cal.build_calendar("2026-11-03", date(2026, 6, 14))
    assert c["forecast_start_month"] == "2026-06"
    assert c["forecast_end_month"] == "2026-11"
    assert c["month_count"] == 6
    assert c["override_used"] is False
    months = [m["forecast_month"] for m in c["months"]]
    assert months == ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]


def test_partial_current_month_day_aware():
    c = cal.build_calendar("2026-11-03", date(2026, 6, 14))
    june = c["months"][0]
    assert june["is_partial_current_month"] is True
    # (30 - 14 + 1) / 30 = 17/30
    assert june["month_remaining_fraction"] == "0.5667"
    # later months are full
    assert c["months"][1]["month_remaining_fraction"] == "1.0000"


def test_override_start_month():
    c = cal.build_calendar("2026-11-03", date(2026, 6, 14), override_start_month="2026-08")
    assert c["forecast_start_month"] == "2026-08"
    assert c["override_used"] is True
    months = [m["forecast_month"] for m in c["months"]]
    assert months[0] == "2026-08" and "2026-06" not in months
    # override month != system month -> not partial
    assert c["months"][0]["is_partial_current_month"] is False


def test_helpers():
    assert cal.add_months("2026-11", 1) == "2026-12"
    assert cal.add_months("2026-12", 1) == "2027-01"
    assert cal.months_between("2026-06", "2026-08") == ["2026-06", "2026-07", "2026-08"]
    assert cal.days_in_month("2026-02") == 28
    assert cal.days_in_month("2026-06") == 30
