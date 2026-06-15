"""Staffing daily rate: latest complete month / weekdays; partial month excluded; volatility flag."""
from decimal import Decimal

from construction_financial_review.forecast_cost_frequency import daily_rate as dr
from construction_financial_review.forecast_cost_frequency import weekday_calendar as wc

CFG = {}


def _ma(items):
    return [{"month": m, "amount_decimal_string": str(a), "entry_count": e} for m, a, e in items]


def test_prior_complete_month_weekday_normalized_rate():
    wd = wc.weekdays_in_month("2026-05")
    ma = _ma([("2026-05", str(1000 * wd), wd)])
    r = dr.compute(ma, "2026-05", CFG, "tropical", "K", "10-01-302", "LAB")
    assert r["latest_complete_month"] == "2026-05"
    assert r["latest_complete_month_weekdays"] == wd
    assert Decimal(r["daily_rate"]) == Decimal("1000")


def test_partial_current_month_not_used_as_basis():
    wd = wc.weekdays_in_month("2026-05")
    # June 2026 is after the latest-complete boundary -> must NOT be the rate basis
    ma = _ma([("2026-05", str(1000 * wd), wd), ("2026-06", "999999", 5)])
    r = dr.compute(ma, "2026-05", CFG, "tropical", "K", "10-01-302", "LAB")
    assert r["latest_complete_month"] == "2026-05"
    assert Decimal(r["daily_rate"]) == Decimal("1000")


def test_rate_volatility_flagged():
    # latest month rate >> trailing-6mo rate => volatile
    rows = [("2025-12", "100", 1), ("2026-01", "100", 1), ("2026-02", "100", 1),
            ("2026-03", "100", 1), ("2026-04", "100", 1), ("2026-05", "100000", 20)]
    r = dr.compute(_ma(rows), "2026-05", CFG, "tropical", "K", "10-01-302", "LAB")
    assert r["rate_volatility_flag"] is True


def test_no_complete_actuals_yields_null_rate():
    r = dr.compute([], "2026-05", CFG, "tropical", "K", "10-01-302", "LAB")
    assert r["daily_rate"] is None
    assert r["daily_rate_basis"] == "no_complete_month_actuals"
