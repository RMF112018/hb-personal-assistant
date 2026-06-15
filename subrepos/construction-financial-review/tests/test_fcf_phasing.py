"""Shared phasing logic: weekday-driven staffing projection + scale-to-CTC preserves shape."""
from decimal import Decimal

from construction_financial_review.forecast_cost_frequency import monthly_frequency_phasing as ph

MONTHS = ["2026-06", "2026-07", "2026-08"]   # weekdays 22 / 23 / 21


def test_staffing_projection_tracks_weekday_count():
    proj = ph.staffing_projection("1000", MONTHS)   # $1000/weekday
    assert proj["2026-06"] == Decimal("22000")
    assert proj["2026-07"] == Decimal("23000")
    assert proj["2026-08"] == Decimal("21000")
    assert proj["2026-07"] > proj["2026-06"] > proj["2026-08"]


def test_scale_to_ctc_sums_exactly_and_preserves_shape():
    raw = ph.staffing_projection("1000", MONTHS)     # total 66000
    scaled, flag, factor = ph.scale_to_ctc(raw, "33000")
    assert flag is True and factor == Decimal("0.5")
    assert sum(scaled.values()) == Decimal("33000")
    # weekday shape preserved: month-to-month ratios unchanged
    assert scaled["2026-07"] / scaled["2026-06"] == raw["2026-07"] / raw["2026-06"]


def test_phasing_weight_vector_weekday_for_staffing_else_none():
    v = ph.phasing_weight_vector("weekly_internal_staffing", MONTHS)
    assert v is not None and abs(sum(v.values()) - Decimal("1")) < Decimal("0.000000001")
    assert ph.phasing_weight_vector("one_time_or_milestone", MONTHS) is None
    assert ph.phasing_weight_vector("inactive_or_complete", MONTHS) is None


def test_phasing_confidence_staffing_is_high():
    assert ph.phasing_confidence("weekly_internal_staffing", "low", True) == "high"
    assert ph.phasing_confidence("monthly_observed", "high", False) == "low"
