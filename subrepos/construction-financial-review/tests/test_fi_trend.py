"""Trend analyzer: acceleration, deceleration, credits/deductive, late emergence."""
from construction_financial_review.forecast_intelligence import trend


def _months(values, start_year=2025, start_month=1):
    out = []
    y, m = start_year, start_month
    for v in values:
        out.append({"month": f"{y:04d}-{m:02d}", "amount_decimal_string": str(v),
                    "actual_period_bucket": "through_may_2026"})
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def test_accelerating_supports_overrun():
    # prior 3mo ~100/mo, recent 3mo ~300/mo
    months = _months([100, 100, 100, 300, 300, 300])
    r = trend.analyze(months, "2026-05-26", "tropical", "K")
    assert r["burn_acceleration_class"] == "accelerating"
    assert r["trend_signal"] == "supports_overrun"


def test_decelerating_supports_decrease():
    months = _months([300, 300, 300, 50, 50, 50])
    r = trend.analyze(months, "2026-05-26", "tropical", "K")
    assert r["burn_acceleration_class"] == "decelerating"
    assert r["trend_signal"] == "supports_decrease"


def test_credits_deductive_detected():
    months = _months([100, 100, 100, 100, 100, -50])
    r = trend.analyze(months, "2026-05-26", "tropical", "K")
    assert r["credits_deductive_pattern"] is True


def test_sparse_actuals_review():
    months = _months([100, 100])
    r = trend.analyze(months, "2026-05-26", "tropical", "K")
    assert r["months_of_completed_actuals"] == 2
    assert r["trend_signal"] == "review"


def test_recency_gap_computed():
    months = _months([100] * 6, start_year=2025, start_month=1)  # last month 2025-06
    r = trend.analyze(months, "2026-05-26", "tropical", "K")
    assert r["recency_gap_months"] == 11    # 2025-06 -> 2026-05
