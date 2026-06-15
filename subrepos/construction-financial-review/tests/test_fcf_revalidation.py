"""Cadence revalidation: surfaces a change when the recent window differs; staffing override wins."""
from construction_financial_review.forecast_cost_frequency import frequency_revalidation as rv

CFG = {"cadence_change_recent_months": 3, "monthly_frequency_entry_count_threshold": 1,
       "bi_monthly_entry_count_threshold": 2, "weekly_entry_count_threshold": 4}


def test_cadence_change_detected_when_recent_more_frequent():
    detected = {"observed_frequency_class": "monthly_observed",
                "entry_count_by_month": {"2026-03": 1, "2026-04": 4, "2026-05": 5}}
    out = rv.revalidate(detected, CFG, "2026-05", False, "tropical", "K", "10-01-302")
    assert out["cadence_change_detected"] is True
    assert out["revalidated_effective_frequency_class"] in ("twice_monthly_observed", "weekly_observed")


def test_no_change_when_recent_consistent():
    detected = {"observed_frequency_class": "monthly_observed",
                "entry_count_by_month": {"2026-03": 1, "2026-04": 1, "2026-05": 1}}
    out = rv.revalidate(detected, CFG, "2026-05", False, "tropical", "K", "10-01-302")
    assert out["cadence_change_detected"] is False


def test_staffing_override_is_effective_class():
    detected = {"observed_frequency_class": "monthly_observed",
                "entry_count_by_month": {"2026-05": 1}}
    out = rv.revalidate(detected, CFG, "2026-05", True, "tropical", "K", "10-01-302")
    assert out["revalidated_effective_frequency_class"] == "weekly_internal_staffing"
