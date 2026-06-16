"""Cadence classification from entry counts + monthly-aggregate fallback behavior."""
from construction_financial_review.forecast_cost_frequency import frequency_detect as fd

CFG = {"minimum_months_for_observed_frequency": 3, "monthly_frequency_entry_count_threshold": 1,
       "bi_monthly_entry_count_threshold": 2, "weekly_entry_count_threshold": 4,
       "cadence_change_recent_months": 3}
BOUNDARY = "2026-05"
MONTHS6 = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]
TXN = ["2026-01-05", "2026-02-05"]   # presence => transaction-level available


def _ma(counts, months=MONTHS6):
    return [{"month": m, "amount_decimal_string": "100", "entry_count": c} for m, c in zip(months, counts)]


def test_monthly_observed():
    d = fd.classify(_ma([1, 1, 1, 1, 1, 1]), TXN, BOUNDARY, CFG, False)
    assert d["observed_frequency_class"] == "monthly_observed"


def test_twice_monthly_observed():
    d = fd.classify(_ma([2, 2, 2, 2, 2, 2]), TXN, BOUNDARY, CFG, False)
    assert d["observed_frequency_class"] == "twice_monthly_observed"


def test_weekly_observed():
    d = fd.classify(_ma([4, 5, 4, 5, 4, 5]), TXN, BOUNDARY, CFG, False)
    assert d["observed_frequency_class"] == "weekly_observed"


def test_irregular_high_dispersion():
    d = fd.classify(_ma([1, 1, 1, 1, 1, 10]), TXN, BOUNDARY, CFG, False)
    assert d["observed_frequency_class"] == "irregular"


def test_one_time_or_milestone():
    d = fd.classify([{"month": "2026-04", "amount_decimal_string": "5000", "entry_count": 1}],
                    TXN, BOUNDARY, CFG, False)
    assert d["observed_frequency_class"] == "one_time_or_milestone"


def test_inactive_or_complete_when_stale():
    d = fd.classify(_ma([3, 3, 3], ["2024-01", "2024-02", "2024-03"]), TXN, BOUNDARY, CFG, False)
    assert d["observed_frequency_class"] == "inactive_or_complete"


def test_insufficient_evidence_below_minimum_months():
    d = fd.classify(_ma([3, 3], ["2026-04", "2026-05"]), TXN, BOUNDARY, CFG, False)
    assert d["observed_frequency_class"] == "insufficient_evidence"


def test_monthly_aggregate_fallback_never_infers_weekly_for_nonstaffing():
    # entry counts look weekly but NO transaction dates -> capped at monthly, fallback flagged
    d = fd.classify(_ma([4, 4, 4, 4, 4, 4]), [], BOUNDARY, CFG, is_staffing=False)
    assert d["monthly_aggregate_fallback_used"] is True
    assert d["observed_frequency_class"] == "monthly_observed"
    assert d["frequency_confidence"] == "low"
