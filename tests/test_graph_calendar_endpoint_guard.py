"""Phase 07B Prompt 03 — Microsoft Graph calendar read-only endpoint guard.

Proves the calendar endpoint contract loads GET-only / body-excluded, that every
allowlisted GET is permitted, every mutation verb/path is refused *before* HTTP,
the blocked error is sanitized, and the in-process no-writeback self-test passes.
"""

from __future__ import annotations

import pytest

from hb_assistant.graph.calendar_endpoint_guard import (
    CalendarMutationBlockedError,
    assert_calendar_request_allowed,
    load_calendar_endpoint_contract,
    run_calendar_no_writeback_self_test,
)


def test_contract_loads_get_only_and_body_excluded() -> None:
    c = load_calendar_endpoint_contract(refresh=True)
    assert c.allowed_methods == frozenset({"GET"})
    assert {"POST", "PATCH", "DELETE", "PUT"} <= c.forbidden_methods
    # Event description / join URL never requested.
    assert "body" not in c.event_metadata_select
    assert "bodyPreview" not in c.event_metadata_select
    assert "onlineMeeting" not in c.event_metadata_select
    # Private-event handling depends on the (valid-for-event) sensitivity field.
    assert "sensitivity" in c.event_metadata_select


@pytest.mark.parametrize(
    "path",
    [
        "/me",
        "/me/calendar",
        "/me/calendars",
        "/me/calendars/AAA",
        "/me/calendarView",
        "/me/calendar/calendarView",
        "/me/calendars/AAA/calendarView",
        "/me/events",
        "/me/events/AAA",
        "/me/calendar/events",
        "/me/calendars/AAA/events",
        # Query string + absolute Graph root must normalize and still pass.
        "/me/calendarView?startDateTime=2026-01-01T00:00:00Z&endDateTime=2026-12-31T23:59:59Z",
        "https://graph.microsoft.com/v1.0/me/calendarView",
    ],
)
def test_allowlisted_get_is_permitted(path: str) -> None:
    assert assert_calendar_request_allowed("GET", path) is None


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "PUT"])
def test_forbidden_methods_are_blocked_on_any_path(method: str) -> None:
    # Even on an otherwise GET-readable event, a mutating verb is refused.
    with pytest.raises(CalendarMutationBlockedError):
        assert_calendar_request_allowed(method, "/me/events/AAA")


@pytest.mark.parametrize(
    "path",
    [
        "/me/events",  # POST create
        "/me/calendar/events",
        "/me/calendars/AAA/events",
        "/me/calendars",  # POST create calendar
        "/me/events/AAA/accept",
        "/me/events/AAA/decline",
        "/me/events/AAA/tentativelyAccept",
        "/me/events/AAA/cancel",
        "/me/events/AAA/forward",
        "/me/events/AAA/snoozeReminder",
        "/me/events/AAA/dismissReminder",
    ],
)
def test_mutation_paths_blocked_with_post(path: str) -> None:
    with pytest.raises(CalendarMutationBlockedError):
        assert_calendar_request_allowed("POST", path)


def test_unknown_get_path_is_blocked() -> None:
    with pytest.raises(CalendarMutationBlockedError):
        assert_calendar_request_allowed("GET", "/me/drive/root")


def test_blocked_error_is_sanitized() -> None:
    try:
        assert_calendar_request_allowed("POST", "/me/events/AAA/cancel")
    except CalendarMutationBlockedError as e:
        assert e.method == "POST"
        assert e.path == "/me/events/AAA/cancel"
        assert e.reason
        # No tokens/headers/content carried on the exception.
        assert "Bearer" not in str(e)
        assert "access_token" not in str(e)
    else:  # pragma: no cover
        raise AssertionError("expected CalendarMutationBlockedError")


def test_self_test_passes_with_no_anomalies() -> None:
    result = run_calendar_no_writeback_self_test()
    assert result["passed"] is True
    assert result["anomalies"] == []
    assert result["read_paths_allowed"] > 0
    assert result["mutation_attempts_blocked"] > 0
