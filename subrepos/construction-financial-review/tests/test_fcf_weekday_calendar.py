"""Weekday calendar: Mon-Fri counts per month + normalized weekday weight vector."""
from decimal import Decimal

from construction_financial_review.forecast_cost_frequency import weekday_calendar as wc


def test_weekday_counts_known_months():
    assert wc.weekdays_in_month("2026-06") == 22
    assert wc.weekdays_in_month("2026-07") == 23
    assert wc.weekdays_in_month("2026-08") == 21


def test_weekday_weight_vector_normalized_and_tracks_weekdays():
    months = ["2026-06", "2026-07", "2026-08"]
    v = wc.weekday_weight_vector(months)
    assert abs(sum(v.values()) - Decimal("1")) < Decimal("0.000000001")
    # July (23 weekdays) carries more than June (22) carries more than August (21)
    assert v["2026-07"] > v["2026-06"] > v["2026-08"]


def test_months_between_inclusive():
    assert wc.months_between("2026-06", "2026-09") == ["2026-06", "2026-07", "2026-08", "2026-09"]
