"""Normalized CalendarEvent model (from calendarView) with redaction and source links."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .redaction import hash_value, redact_location


class CalendarEvent(BaseModel):
    id: str
    ical_uid: Optional[str] = None
    subject_redacted: Optional[str] = None
    organizer_hash: Optional[str] = None
    attendees_hashes: List[str] = Field(default_factory=list)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    timezone: Optional[str] = None
    location_redacted: Optional[str] = None
    is_online_meeting: bool = False
    online_meeting_link: Optional[str] = None
    web_link: Optional[str] = None
    has_attachments: bool = False
    is_cancelled: bool = False
    is_private: bool = False
    source_record_id: Optional[int] = None
    source_links: List[dict] = Field(default_factory=list)

    @classmethod
    def from_graph_event(cls, ev: dict) -> "CalendarEvent":
        org = ev.get("organizer", {}).get("emailAddress", {}).get("address")
        return cls(
            id=ev.get("id"),
            ical_uid=ev.get("iCalUId"),
            subject_redacted=f"[redacted:{hash_value(ev.get('subject'))}]" if ev.get("subject") else None,
            organizer_hash=hash_value(org) if org else None,
            attendees_hashes=[hash_value(a.get("emailAddress", {}).get("address")) for a in ev.get("attendees", []) if a.get("emailAddress")],
            start=ev.get("start", {}).get("dateTime"),
            end=ev.get("end", {}).get("dateTime"),
            timezone=ev.get("start", {}).get("timeZone"),
            location_redacted=redact_location(ev.get("location", {}).get("displayName")),
            is_online_meeting=ev.get("isOnlineMeeting", False),
            online_meeting_link=ev.get("onlineMeeting", {}).get("joinUrl") if ev.get("onlineMeeting") else None,
            web_link=ev.get("webLink"),
            has_attachments=ev.get("hasAttachments", False),
            is_cancelled=ev.get("isCancelled", False),
            is_private=ev.get("sensitivity") == "private",
        )
