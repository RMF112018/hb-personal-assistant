"""Phase 07B Prompt 03 — read-only Microsoft Graph calendar client.

Verifies the guarded client issues only allowlisted GETs, applies a body-free /
join-URL-free ``$select``, refuses a mutation path *before* any HTTP call, and
exposes no calendar-mutation method.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from hb_assistant.graph.calendar_endpoint_guard import CalendarMutationBlockedError
from hb_assistant.graph.calendar_readonly_client import ReadOnlyCalendarClient


class FakeHttp:
    """Records calls; stands in for GraphHttpClient (GET surface only)."""

    def __init__(self) -> None:
        self.get_calls: list[tuple[str, Optional[dict[str, Any]]]] = []
        self.pages_calls: list[tuple[str, Optional[dict[str, Any]], Optional[int]]] = []

    def get(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        scopes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        self.get_calls.append((path, params))
        return {"id": "X", "userPrincipalName": "u@example.com"}

    def get_all_pages(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        scopes: Optional[list[str]] = None,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
    ):
        self.pages_calls.append((path, params, max_items))
        yield {"id": "event1"}


def _client() -> tuple[ReadOnlyCalendarClient, FakeHttp]:
    http = FakeHttp()
    return ReadOnlyCalendarClient(http), http  # type: ignore[arg-type]


def test_list_calendar_view_is_windowed_and_body_free() -> None:
    client, http = _client()
    client.list_calendar_view(
        start="2026-01-01T00:00:00Z", end="2026-12-31T23:59:59Z", top=10, max_items=10
    )
    path, params, _ = http.pages_calls[0]
    assert path == "/me/calendarView"
    assert params["startDateTime"] == "2026-01-01T00:00:00Z"
    assert params["endDateTime"] == "2026-12-31T23:59:59Z"
    fields = params["$select"].split(",")
    # Event body / preview / online-meeting join URL never selected.
    assert "body" not in fields
    assert "bodyPreview" not in fields
    assert "onlineMeeting" not in fields
    assert "sensitivity" in fields  # drives private-event handling


def test_get_me_is_guarded_get() -> None:
    client, http = _client()
    client.get_me()
    assert http.get_calls[0][0] == "/me"


def test_guarded_request_refuses_mutation_before_http() -> None:
    client, http = _client()
    with pytest.raises(CalendarMutationBlockedError):
        client._guarded_get("/me/events/AAA/cancel")
    # HTTP never touched.
    assert http.get_calls == []
    assert http.pages_calls == []


def test_client_exposes_no_mutation_method() -> None:
    forbidden_fragments = (
        "accept",
        "decline",
        "tentative",
        "cancel",
        "forward",
        "snooze",
        "dismiss",
        "send",
        "create",
        "update",
        "delete",
        "move",
        "copy",
    )
    public = [name for name in dir(ReadOnlyCalendarClient) if not name.startswith("_")]
    leaks = [name for name in public if any(frag in name.lower() for frag in forbidden_fragments)]
    assert not leaks, f"read-only client exposes mutation-like methods: {leaks}"
