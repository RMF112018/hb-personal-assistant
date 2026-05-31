"""Phase 07B — read-only Microsoft Graph calendar client.

A thin GET-only wrapper over :class:`GraphHttpClient`. Every request is routed
through :func:`assert_calendar_request_allowed` *before* any HTTP call, so a
calendar mutation can never leave this process. Event listings use the
metadata-first ``$select`` set from the Phase 07B contract, which structurally
excludes the event ``body``/description and the online-meeting join URL.

This client exposes **only** read methods (identity, windowed event listing).
It intentionally has no calendar-mutation method (no event create/update/delete,
attendee accept/decline/tentative response, organizer cancel, forward, or
reminder snooze/dismiss) — read-only is enforced by both the absence of those
methods and the per-request guard.
"""

from __future__ import annotations

from typing import Any, Optional

from hb_assistant.graph.calendar_endpoint_guard import (
    CalendarEndpointContract,
    assert_calendar_request_allowed,
    load_calendar_endpoint_contract,
)
from hb_assistant.graph.http_client import GraphHttpClient

# Graph $top valid range is 1..1000; keep default conservative for bounded reads.
_DEFAULT_PAGE_SIZE = 25
_MAX_TOP = 1000


class ReadOnlyCalendarClient:
    """GET-only calendar reader: identity probe + windowed event metadata."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        *,
        contract: Optional[CalendarEndpointContract] = None,
    ) -> None:
        self._client = http_client
        self._contract = contract or load_calendar_endpoint_contract()

    # --- guarded request primitives ----------------------------------------

    def _guarded_get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        assert_calendar_request_allowed("GET", path, contract=self._contract)
        return self._client.get(path, params=params)

    def _guarded_pages(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        *,
        max_items: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        assert_calendar_request_allowed("GET", path, contract=self._contract)
        return list(self._client.get_all_pages(path, params=params, max_items=max_items))

    # --- $select helpers ----------------------------------------------------

    def _event_select(self) -> str:
        return ",".join(self._contract.event_metadata_select)

    @staticmethod
    def _clamp_top(top: int) -> int:
        return max(1, min(int(top), _MAX_TOP))

    # --- read operations ----------------------------------------------------

    def get_me(self) -> dict[str, Any]:
        """Identity / mailbox-owner probe (``GET /me``)."""
        return self._guarded_get("/me", {"$select": "id,displayName,userPrincipalName,mail"})

    def list_calendar_view(
        self,
        *,
        start: str,
        end: str,
        top: int = _DEFAULT_PAGE_SIZE,
        max_items: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """List event **metadata** (no body, no join URL) for a bounded window.

        ``start``/``end`` are ISO timestamps bounding the ``calendarView`` window;
        the listing is never an unbounded full-calendar backfill.
        """
        params: dict[str, Any] = {
            "startDateTime": start,
            "endDateTime": end,
            "$top": self._clamp_top(top),
            "$select": self._event_select(),
            "$orderby": "start/dateTime",
        }
        return self._guarded_pages("/me/calendarView", params, max_items=max_items)
