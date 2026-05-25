"""CalendarClient: calendarView over configured window (yesterday/today/next 2 business days)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from hb_assistant.config.loader import load_config
from hb_assistant.normalize.calendar_event import CalendarEvent

from .http_client import GraphHttpClient


class CalendarClient:
    def __init__(self, http_client: GraphHttpClient, cfg=None):
        self.client = http_client
        self.cfg = cfg or load_config()

    def _window(self) -> tuple[str, str]:
        now = datetime.now(timezone.utc)
        # Simple window per spec (yesterday/today/next 2 business days)
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = (now + timedelta(days=3)).replace(hour=23, minute=59, second=59, microsecond=0)
        return start.isoformat(), end.isoformat()

    def list_events(self, top: int = 10) -> List[CalendarEvent]:
        start, end = self._window()
        url = f"/me/calendarView?startDateTime={start}&endDateTime={end}&$top={top}&$select=id,subject,organizer,start,end,location,isCancelled,isOnlineMeeting,webLink,hasAttachments,iCalUId"
        data = self.client.get(url)
        events = []
        for ev in data.get("value", []):
            events.append(CalendarEvent.from_graph_event(ev))
        return events
