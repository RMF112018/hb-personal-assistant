"""Derived finish-float helpers."""

from __future__ import annotations

from hb_assistant.construction.analytics.schedule_float_derivation import (
    derive_finish_float,
    parse_schedule_options,
    supports_finish_float_derivation,
)


def test_parse_schedule_options_normalizes_threshold() -> None:
    opts = parse_schedule_options(
        {
            "ComputeTotalFloatType": "Finish Float = Late Finish - Early Finish",
            "CriticalActivityPathType": "Critical Float",
            "CriticalActivityFloatThreshold": "0",
            "CalculateFloatBasedOnFinishDate": "1",
        }
    )
    assert opts["critical_activity_float_threshold"] == 0.0
    assert opts["calculate_float_based_on_finish_date"] == 1
    assert supports_finish_float_derivation(opts)


def test_derive_finish_float_from_remaining_dates() -> None:
    opts = parse_schedule_options(
        {
            "ComputeTotalFloatType": "Finish Float = Late Finish - Early Finish",
            "CriticalActivityPathType": "Critical Float",
            "CriticalActivityFloatThreshold": "0",
        }
    )
    activity = {
        "remaining_early_finish": "2027-03-12T17:00:00",
        "remaining_late_finish": "2027-07-29T17:00:00",
        "calendar_id": "C1",
    }
    calendars = {"C1": {"hours_per_day": "8"}}
    derived = derive_finish_float(activity, options=opts, calendars_by_id=calendars)
    assert derived["derived_float_basis"] == "remaining_late_finish_minus_remaining_early_finish"
    assert float(derived["derived_total_float_days"]) > 0
    assert derived["derived_is_critical_by_float_threshold"] == 0


def test_derive_finish_float_negative_is_critical_at_threshold_zero() -> None:
    opts = parse_schedule_options(
        {
            "ComputeTotalFloatType": "Finish Float = Late Finish - Early Finish",
            "CriticalActivityPathType": "Critical Float",
            "CriticalActivityFloatThreshold": "0",
        }
    )
    activity = {
        "remaining_early_finish": "2027-03-12T17:00:00",
        "remaining_late_finish": "2027-03-10T17:00:00",
    }
    derived = derive_finish_float(activity, options=opts)
    assert float(derived["derived_total_float_days"]) < 0
    assert derived["derived_is_critical_by_float_threshold"] == 1


def test_unsupported_float_type_returns_empty() -> None:
    opts = parse_schedule_options(
        {"ComputeTotalFloatType": "Start Float = Late Start - Early Start"}
    )
    activity = {
        "remaining_early_finish": "2027-03-12T17:00:00",
        "remaining_late_finish": "2027-07-29T17:00:00",
    }
    assert derive_finish_float(activity, options=opts) == {}
