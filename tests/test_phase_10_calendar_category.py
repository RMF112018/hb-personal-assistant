"""Phase 10 — deterministic calendar category resolution (daily-brief usefulness repair).

Covers the project/internal/needs-review category dimension layered on the existing alias resolver:
exact alias, case-insensitive token, ambiguous→needs_review, internal company/PTO/training,
multiple signals, low-confidence review-safe fallback, the indexed-key short-circuit, and that the
project arm stays consistent with project_aliases.resolve_project (no forked semantics).
"""

from __future__ import annotations

from hb_assistant.construction.second_brain.local_ai.calendar_category import (
    resolve_calendar_category,
)
from hb_assistant.construction.second_brain.local_ai.project_aliases import resolve_project


def test_exact_alias_resolves_to_project() -> None:
    r = resolve_calendar_category(subject="Pre-Submission Bid Review - The Wellington Homes")
    assert r.category == "project"
    assert r.project_key == "the-wellington"
    assert r.needs_review is False
    assert r.confidence >= 0.9
    # Project arm must agree with the canonical resolver (no forked semantics).
    assert r.project_key == resolve_project("Pre-Submission Bid Review - The Wellington Homes")


def test_case_insensitive_token() -> None:
    r = resolve_calendar_category(subject="twn oac")
    assert r.category == "project"
    assert r.project_key == "tropical"
    assert r.matched_alias == "twn"


def test_longest_alias_wins_via_delegation() -> None:
    # "Alton Hilltop" beats "Hilltop"; both map to the one canonical key.
    r = resolve_calendar_category(subject="FW: Alton Hilltop Bi-Weekly")
    assert r.project_key == "alton-hilltop-pbg"
    assert r.category == "project"


def test_pto_is_internal_time_off_not_project() -> None:
    r = resolve_calendar_category(subject="Andrew PTO")
    assert r.category == "internal_time_off"
    assert r.project_key == "__internal_time_off__"
    assert r.needs_review is False


def test_training_is_internal_training() -> None:
    r = resolve_calendar_category(
        subject="LMA Training: Group #2 - Session #5 Clarity & Recognition"
    )
    assert r.category == "internal_training"
    assert r.project_key == "__internal_training__"


def test_financial_forecast_is_internal_company() -> None:
    r = resolve_calendar_category(subject="[DUE TODAY] Project Financial Forecasts")
    assert r.category == "internal_company"
    assert r.project_key == "__internal_company__"


def test_ambiguous_project_like_token_is_needs_review() -> None:
    # A capitalized, project-looking token that is NOT a known alias → review-safe, never invented.
    r = resolve_calendar_category(subject="Northgate Tower Coordination")
    assert r.category == "needs_review"
    assert r.project_key == "__needs_review__"
    assert r.needs_review is True
    assert r.confidence < 0.5
    # And the canonical resolver agrees there is no project match.
    assert resolve_project("Northgate Tower Coordination") is None


def test_unknown_when_no_signal() -> None:
    r = resolve_calendar_category(subject="lunch")
    assert r.category == "unknown"
    assert r.project_key == "__unassigned__"
    assert r.needs_review is False


def test_multiple_signals_project_wins_over_internal() -> None:
    # A real project token outranks a generic internal keyword in the same subject.
    r = resolve_calendar_category(subject="Wellington Leadership Sync")
    assert r.category == "project"
    assert r.project_key == "the-wellington"


def test_indexed_project_key_short_circuits() -> None:
    r = resolve_calendar_category(subject="anything", indexed_project_key="pga-modern-garage")
    assert r.category == "project"
    assert r.project_key == "pga-modern-garage"
    assert r.reason == "indexed_project_key"
    # A sentinel-like indexed value is NOT treated as a real key.
    r2 = resolve_calendar_category(subject="lunch", indexed_project_key="__unassigned__")
    assert r2.category == "unknown"


def test_resolution_carries_no_raw_only_redacted_inputs() -> None:
    # The resolver only ever sees redacted subject/location text; its reason codes are safe enums.
    r = resolve_calendar_category(subject="[redacted-subject]", location="[redacted-loc]")
    assert r.category in {"needs_review", "unknown"}
    assert "redacted" not in r.reason
