"""Phase 10 — weekday-aware daily-brief date/window policy.

Covers Monday weekend/prior-week carryover, Tuesday–Thursday standard adjacent-business-day
windows, Friday next-week prep, weekend skip vs Saturday catch-up of a missed Friday, DST/local
America/New_York dates (not UTC-only), included_dates, explanation, and to_dict serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hb_assistant.construction.second_brain.local_ai.daily_brief_window import (
    LABEL_FRIDAY,
    LABEL_MONDAY,
    LABEL_SKIPPED_WEEKEND,
    LABEL_STANDARD,
    compute_daily_brief_window,
)

TZ = "America/New_York"


def _run(y: int, m: int, d: int, hh: int = 5, mm: int = 0) -> datetime:
    """Naive local run datetime (interpreted in America/New_York by the policy)."""
    return datetime(y, m, d, hh, mm)


# --- Monday carryover ----------------------------------------------------------


def test_monday_lookback_includes_prior_friday_and_weekend() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 15), TZ)  # Monday
    assert w.label == LABEL_MONDAY
    assert w.run_weekday == "Monday"
    assert w.previous_business_day == "2026-06-12"  # prior Friday
    assert w.next_business_day == "2026-06-16"  # Tuesday
    assert w.lookback_start.startswith("2026-06-12T00:00:00")
    assert w.lookback_end.startswith("2026-06-15T05:00:00")
    # weekend days fall inside the brief window
    assert "2026-06-13" in w.included_dates and "2026-06-14" in w.included_dates
    assert w.carryover_section_label == "Prior Week / Weekend Carryover"


def test_monday_lookahead_covers_workweek() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 15), TZ)
    assert w.calendar_prep_end.startswith("2026-06-19")  # Friday of run week
    assert "carryover" in w.explanation.lower()


# --- Tuesday–Thursday standard -------------------------------------------------


def test_tuesday_standard_window() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 16), TZ)  # Tuesday
    assert w.label == LABEL_STANDARD
    assert w.previous_business_day == "2026-06-15"  # Monday
    assert w.next_business_day == "2026-06-17"  # Wednesday
    assert w.lookback_start.startswith("2026-06-15T00:00:00")
    assert w.carryover_section_label is None


def test_wednesday_standard_window() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 17), TZ)  # Wednesday
    assert w.label == LABEL_STANDARD
    assert w.previous_business_day == "2026-06-16"  # Tuesday
    assert w.next_business_day == "2026-06-18"  # Thursday
    assert w.lookback_end.startswith("2026-06-17T05:00:00")


def test_thursday_standard_window() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 18), TZ)  # Thursday
    assert w.label == LABEL_STANDARD
    assert w.previous_business_day == "2026-06-17"  # Wednesday
    assert w.next_business_day == "2026-06-19"  # Friday
    assert w.calendar_prep_end.startswith("2026-06-19")  # next business day


# --- Friday next-week prep -----------------------------------------------------


def test_friday_lookahead_covers_following_workweek() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 19), TZ)  # Friday
    assert w.label == LABEL_FRIDAY
    assert w.previous_business_day == "2026-06-18"  # Thursday
    assert w.next_business_day == "2026-06-22"  # following Monday
    assert w.lookback_start.startswith("2026-06-18T00:00:00")
    assert w.calendar_prep_end.startswith("2026-06-26")  # next Friday horizon
    assert w.carryover_section_label == "Next Week Prep"
    # weekend + next workweek included
    assert "2026-06-22" in w.included_dates and "2026-06-26" in w.included_dates


# --- weekend skip vs catch-up --------------------------------------------------


def test_saturday_catch_up_of_missed_friday_uses_friday_policy() -> None:
    # Friday 2026-06-19 not yet successful → Saturday catch-up runs the Friday brief.
    w = compute_daily_brief_window(
        _run(2026, 6, 20), TZ, last_successful_date="2026-06-18"
    )  # Saturday
    assert w.label == LABEL_FRIDAY
    assert w.run_date == "2026-06-19"  # resolved to the missed Friday
    assert w.catch_up is True
    assert w.calendar_prep_end.startswith("2026-06-26")


def test_sunday_catch_up_with_no_history_uses_friday_policy() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 21), TZ, last_successful_date=None)  # Sunday
    assert w.label == LABEL_FRIDAY
    assert w.run_date == "2026-06-19"
    assert w.catch_up is True


def test_fresh_saturday_skips_when_friday_already_succeeded() -> None:
    w = compute_daily_brief_window(
        _run(2026, 6, 20), TZ, last_successful_date="2026-06-19"
    )  # Saturday, Friday already ran
    assert w.label == LABEL_SKIPPED_WEEKEND
    assert w.is_skipped_weekend is True


# --- DST / local-date correctness ----------------------------------------------


def test_dst_summer_offset_is_edt() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 15), TZ)  # June → EDT
    assert w.lookback_end.endswith("-04:00")


def test_winter_offset_is_est() -> None:
    w = compute_daily_brief_window(_run(2026, 1, 5), TZ)  # Monday Jan 5 2026 → EST
    assert w.lookback_end.endswith("-05:00")
    assert w.label == LABEL_MONDAY


def test_utc_input_maps_to_local_new_york_date() -> None:
    # 09:00 UTC on Monday 2026-06-15 == 05:00 EDT same local date (not UTC-only).
    w = compute_daily_brief_window(datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc), TZ)
    assert w.run_date == "2026-06-15"
    assert w.lookback_end.startswith("2026-06-15T05:00:00")
    assert w.lookback_end.endswith("-04:00")


# --- serialization -------------------------------------------------------------


def test_to_dict_has_all_policy_fields() -> None:
    w = compute_daily_brief_window(_run(2026, 6, 15), TZ)
    d = w.to_dict()
    for key in (
        "run_date",
        "run_weekday",
        "label",
        "previous_business_day",
        "next_business_day",
        "lookback_start",
        "lookback_end",
        "lookahead_start",
        "lookahead_end",
        "calendar_prep_start",
        "calendar_prep_end",
        "included_dates",
        "explanation",
    ):
        assert key in d, key
    assert isinstance(d["included_dates"], list) and d["included_dates"]
