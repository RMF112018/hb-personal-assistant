"""Precedence-aware consumer read models for email/calendar (Pass 2).

Every downstream consumer (daily brief, meeting prep, model-context packets, follow-up
windows, relationship extraction, retrieval, the email/calendar endpoints) routes through
these selectors so the **final structured projection layer is preferred over raw-landing and
legacy/redacted metadata by source-quality rank**, and a lower-quality row can never silently
downgrade consumer context.

Selection order (highest wins; the chosen tier is returned so it is testable):

```
structured_full     graph_full_body / graph_full_event_body structured projection row
structured_preview  graph_body_preview_only structured projection row
structured_legacy    redacted_legacy_projection / metadata_only structured row
raw_landing          raw V42 landing row (no structured projection yet)
legacy_metadata      legacy redacted/metadata index/summary only
none                 nothing available
```

These objects are **redacted-safe**: they carry business metadata, availability flags, child
collections (recipients/attendees), and a `body_ref` link — never the body text itself. Raw
body text is fetched local-private only via the explicit `load_body(...)` accessor, which
writes a `raw_content_access_events` audit row.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field
from typing import Any

from .source_quality import (
    CALENDAR_FULL_BODY,
    EMAIL_FULL_BODY,
    EMAIL_PREVIEW_ONLY,
    rank,
)

# Tier labels (in descending preference within a family): any structured projection row is
# preferred over the raw V42 landing row, so structured_legacy outranks raw_landing.
TIER_STRUCTURED_FULL = "structured_full"
TIER_STRUCTURED_PREVIEW = "structured_preview"
TIER_STRUCTURED_LEGACY = "structured_legacy"
TIER_RAW_LANDING = "raw_landing"
TIER_LEGACY_METADATA = "legacy_metadata"
TIER_NONE = "none"


def _structured_tier(source_quality: str | None) -> str:
    if source_quality in (EMAIL_FULL_BODY, CALENDAR_FULL_BODY):
        return TIER_STRUCTURED_FULL
    if source_quality == EMAIL_PREVIEW_ONLY:
        return TIER_STRUCTURED_PREVIEW
    return TIER_STRUCTURED_LEGACY


def _loads(value: Any, default: Any) -> Any:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


# --- email message --------------------------------------------------------------


@dataclass
class EmailMessageContext:
    selected_source: str
    source_quality: str | None
    message_id_hash: str | None = None
    conversation_id_hash: str | None = None
    thread_ref: str | None = None
    project_key: str | None = None
    subject: str | None = None
    from_name: str | None = None
    from_address: str | None = None
    sent_at_utc: str | None = None
    received_at_utc: str | None = None
    has_body_text: bool = False
    body_text_chars: int = 0
    has_body_html: bool = False
    recipient_count: int = 0
    attachment_count: int = 0
    recipients: list[dict[str, Any]] = field(default_factory=list)
    raw_email_id: str | None = None  # body_ref

    @property
    def available(self) -> bool:
        return self.selected_source != TIER_NONE

    def load_body(self, store: Any, *, purpose: str = "consumer_read") -> dict[str, Any]:
        """Local-private body fetch for raw-permitted callers. Writes an access-audit row and
        returns body fields. Never call this from a redacted outbound surface."""
        if not self.raw_email_id and not self.message_id_hash:
            return {}
        raw = store.get_email_message_raw_content(message_id_hash=self.message_id_hash)
        with contextlib.suppress(Exception):
            store.record_raw_content_access_event(
                source_family="email",
                endpoint_or_command="read_models.email_message.load_body",
                source_ref_hash=self.message_id_hash,
                raw_content_included=1,
                purpose=purpose,
            )
        if not raw:
            return {}
        return {
            "subject": raw.get("subject"),
            "body_text": raw.get("body_text"),
            "body_html": raw.get("body_html"),
            "body_preview": raw.get("body_preview"),
        }


def select_email_message_context(store: Any, *, message_id_hash: str | None) -> EmailMessageContext:
    if not message_id_hash:
        return EmailMessageContext(selected_source=TIER_NONE, source_quality=None)
    s = store.get_email_message_structured(message_id_hash=message_id_hash)
    if s:
        pid = s.get("projection_id")
        recips = store.list_email_message_recipients_structured(parent_projection_id=pid)
        return EmailMessageContext(
            selected_source=_structured_tier(s.get("source_quality")),
            source_quality=s.get("source_quality"),
            message_id_hash=s.get("message_id_hash"),
            conversation_id_hash=s.get("conversation_id_hash"),
            thread_ref=s.get("thread_ref"),
            project_key=s.get("project_key"),
            subject=s.get("subject"),
            from_name=s.get("from_name"),
            from_address=s.get("from_address"),
            sent_at_utc=s.get("sent_at_utc"),
            received_at_utc=s.get("received_at_utc"),
            has_body_text=bool(s.get("body_text_available")),
            body_text_chars=int(s.get("body_text_chars") or 0),
            has_body_html=bool(s.get("body_html_available")),
            recipient_count=int(s.get("recipient_count") or 0),
            attachment_count=int(s.get("attachment_count") or 0),
            recipients=[
                {
                    "role": r.get("role"),
                    "name": r.get("name"),
                    "address": r.get("address"),
                    "domain": r.get("domain"),
                }
                for r in recips
            ],
            raw_email_id=s.get("raw_email_id") or s.get("raw_row_id"),
        )
    # fall back to raw landing only when no structured row exists
    raw = store.get_email_message_raw_content(message_id_hash=message_id_hash)
    if raw:
        return EmailMessageContext(
            selected_source=TIER_RAW_LANDING,
            source_quality=raw.get("source_quality"),
            message_id_hash=raw.get("message_id_hash"),
            conversation_id_hash=raw.get("conversation_id_hash"),
            thread_ref=raw.get("conversation_id_hash") or raw.get("message_id_hash"),
            project_key=raw.get("project_key"),
            subject=raw.get("subject"),
            from_name=raw.get("from_name"),
            from_address=raw.get("from_address"),
            sent_at_utc=raw.get("sent_at_utc"),
            received_at_utc=raw.get("received_at_utc"),
            has_body_text=bool((raw.get("body_text") or "").strip()),
            body_text_chars=len(raw.get("body_text") or ""),
            has_body_html=bool((raw.get("body_html") or "").strip()),
            recipient_count=len(raw.get("to") or [])
            + len(raw.get("cc") or [])
            + len(raw.get("bcc") or []),
            recipients=[],
            raw_email_id=raw.get("raw_email_id"),
        )
    return EmailMessageContext(
        selected_source=TIER_NONE, source_quality=None, message_id_hash=message_id_hash
    )


# --- email thread ---------------------------------------------------------------


@dataclass
class ThreadContext:
    selected_source: str
    source_quality: str | None
    thread_ref: str | None = None
    conversation_id_hash: str | None = None
    project_key: str | None = None
    thread_subject: str | None = None
    message_count: int = 0
    participant_count: int = 0
    has_full_body: bool = False
    raw_thread_context_id: str | None = None  # body_ref

    @property
    def available(self) -> bool:
        return self.selected_source != TIER_NONE


def select_thread_context(store: Any, *, thread_ref: str | None) -> ThreadContext:
    if not thread_ref:
        return ThreadContext(selected_source=TIER_NONE, source_quality=None)
    s = store.get_thread_structured(thread_ref=thread_ref)
    if s:
        return ThreadContext(
            selected_source=_structured_tier(s.get("source_quality")),
            source_quality=s.get("source_quality"),
            thread_ref=s.get("thread_ref"),
            conversation_id_hash=s.get("conversation_id_hash"),
            project_key=s.get("project_key"),
            thread_subject=s.get("thread_subject"),
            message_count=int(s.get("message_count") or 0),
            participant_count=int(s.get("participant_count") or 0),
            has_full_body=bool(s.get("has_full_body")),
            raw_thread_context_id=s.get("raw_thread_context_id") or s.get("raw_row_id"),
        )
    raw = store.get_email_thread_raw_context(thread_ref=thread_ref)
    if raw:
        msgs = raw.get("messages") or _loads(raw.get("messages_json"), [])
        any_body = any(
            isinstance(m, dict) and (m.get("body_text") or m.get("body_html"))
            for m in (msgs if isinstance(msgs, list) else [])
        )
        return ThreadContext(
            selected_source=TIER_RAW_LANDING,
            source_quality=raw.get("source_quality"),
            thread_ref=raw.get("thread_ref"),
            conversation_id_hash=raw.get("conversation_id_hash"),
            project_key=raw.get("project_key"),
            thread_subject=raw.get("thread_subject"),
            message_count=int(raw.get("message_count") or 0),
            participant_count=int(raw.get("participant_count") or 0),
            has_full_body=any_body,
            raw_thread_context_id=raw.get("raw_thread_context_id"),
        )
    return ThreadContext(selected_source=TIER_NONE, source_quality=None, thread_ref=thread_ref)


# --- calendar event -------------------------------------------------------------


@dataclass
class EventContext:
    selected_source: str
    source_quality: str | None
    event_index_id: str | None = None
    graph_event_id_hash: str | None = None
    project_key: str | None = None
    subject: str | None = None
    location_display: str | None = None
    organizer_name: str | None = None
    organizer_email: str | None = None
    online_meeting_provider: str | None = None
    has_join_url: bool = False
    join_url_policy: str | None = None
    start_datetime_utc: str | None = None
    end_datetime_utc: str | None = None
    has_body_text: bool = False
    body_text_chars: int = 0
    attendee_count: int = 0
    has_recurrence: bool = False
    attendees: list[dict[str, Any]] = field(default_factory=list)
    raw_calendar_event_id: str | None = None  # body_ref

    @property
    def available(self) -> bool:
        return self.selected_source != TIER_NONE

    def load_body(self, store: Any, *, purpose: str = "consumer_read") -> dict[str, Any]:
        """Local-private agenda/body fetch for raw-permitted callers. Writes an access-audit
        row. The join URL is NEVER returned here (it stays in the raw table under policy)."""
        raw = store.get_calendar_event_raw_content(
            event_index_id=self.event_index_id, graph_event_id_hash=self.graph_event_id_hash
        )
        with contextlib.suppress(Exception):
            store.record_raw_content_access_event(
                source_family="calendar",
                endpoint_or_command="read_models.calendar_event.load_body",
                source_ref_hash=self.graph_event_id_hash,
                raw_content_included=1,
                purpose=purpose,
            )
        if not raw:
            return {}
        return {
            "subject": raw.get("subject"),
            "body_text": raw.get("body_text"),
            "body_html": raw.get("body_html"),
            "body_preview": raw.get("body_preview"),
        }


def select_event_context(
    store: Any, *, event_index_id: str | None = None, graph_event_id_hash: str | None = None
) -> EventContext:
    if not event_index_id and not graph_event_id_hash:
        return EventContext(selected_source=TIER_NONE, source_quality=None)
    s = store.get_event_structured(
        event_index_id=event_index_id, graph_event_id_hash=graph_event_id_hash
    )
    if s:
        pid = s.get("projection_id")
        attendees = store.list_event_attendees_structured(parent_projection_id=pid)
        return EventContext(
            selected_source=_structured_tier(s.get("source_quality")),
            source_quality=s.get("source_quality"),
            event_index_id=s.get("event_index_id"),
            graph_event_id_hash=s.get("graph_event_id_hash"),
            project_key=s.get("project_key"),
            subject=s.get("subject"),
            location_display=s.get("location_display"),
            organizer_name=s.get("organizer_name"),
            organizer_email=s.get("organizer_email"),
            online_meeting_provider=s.get("online_meeting_provider"),
            has_join_url=bool(s.get("has_join_url")),
            join_url_policy=s.get("join_url_policy"),
            start_datetime_utc=s.get("start_datetime_utc"),
            end_datetime_utc=s.get("end_datetime_utc"),
            has_body_text=bool(s.get("body_text_available")),
            body_text_chars=int(s.get("body_text_chars") or 0),
            attendee_count=int(s.get("attendee_count") or 0),
            has_recurrence=bool(s.get("has_recurrence")),
            attendees=[
                {
                    "attendee_type": a.get("attendee_type"),
                    "response_status": a.get("response_status"),
                    "name": a.get("name"),
                    "domain": a.get("domain"),
                }
                for a in attendees
            ],
            raw_calendar_event_id=s.get("raw_calendar_event_id") or s.get("raw_row_id"),
        )
    raw = store.get_calendar_event_raw_content(
        event_index_id=event_index_id, graph_event_id_hash=graph_event_id_hash
    )
    if raw:
        return EventContext(
            selected_source=TIER_RAW_LANDING,
            source_quality=raw.get("source_quality"),
            event_index_id=raw.get("event_index_id"),
            graph_event_id_hash=raw.get("graph_event_id_hash"),
            project_key=raw.get("project_key"),
            subject=raw.get("subject"),
            location_display=raw.get("location_display"),
            organizer_name=raw.get("organizer_name"),
            organizer_email=raw.get("organizer_email"),
            online_meeting_provider=raw.get("online_meeting_provider"),
            has_join_url=bool((raw.get("join_url") or "").strip()),
            join_url_policy=raw.get("join_url_policy"),
            start_datetime_utc=raw.get("start_datetime_utc"),
            end_datetime_utc=raw.get("end_datetime_utc"),
            has_body_text=bool((raw.get("body_text") or "").strip()),
            body_text_chars=len(raw.get("body_text") or ""),
            attendee_count=len(raw.get("attendees") or []),
            has_recurrence=bool(raw.get("recurrence_json")),
            attendees=[],
            raw_calendar_event_id=raw.get("raw_calendar_event_id"),
        )
    return EventContext(
        selected_source=TIER_NONE,
        source_quality=None,
        event_index_id=event_index_id,
        graph_event_id_hash=graph_event_id_hash,
    )


# --- diagnostics ----------------------------------------------------------------


def consumer_source_summary(store: Any, *, project_key: str | None = None) -> dict[str, Any]:
    """Counts (only) of which tier consumers would select per family — for status/evidence."""

    def _summ(rows: list[dict[str, Any]], kind: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in rows:
            tier = _structured_tier(r.get("source_quality"))
            out[tier] = out.get(tier, 0) + 1
        return out

    return {
        "email_message": _summ(
            store.list_email_message_structured(project_key=project_key), "email"
        ),
        "email_thread": _summ(store.list_thread_structured(project_key=project_key), "thread"),
        "calendar_event": _summ(store.list_event_structured(project_key=project_key), "calendar"),
        "rank_ladder": {
            "structured_full": rank(EMAIL_FULL_BODY),
            "structured_preview": rank(EMAIL_PREVIEW_ONLY),
        },
    }


__all__ = [
    "TIER_LEGACY_METADATA",
    "TIER_NONE",
    "TIER_RAW_LANDING",
    "TIER_STRUCTURED_FULL",
    "TIER_STRUCTURED_LEGACY",
    "TIER_STRUCTURED_PREVIEW",
    "EmailMessageContext",
    "EventContext",
    "ThreadContext",
    "consumer_source_summary",
    "select_email_message_context",
    "select_event_context",
    "select_thread_context",
]
