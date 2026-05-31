"""Phase 07B Prompt 04 — bounded calendarView event indexing (read-only, redacted).

Reads a bounded calendarView window through the guarded
:class:`ReadOnlyCalendarClient` and persists **only redacted/hashed metadata** into
the V23 ``calendar_event_index`` / ``calendar_event_attendees`` tables, with a
``calendar_crawl_runs`` receipt and ``calendar_sync_state`` as the run audit trail.

Read-only externally: only ``get_me`` / ``list_calendar_view`` (guarded GETs with a
body-/join-URL-free ``$select``) are issued. The only writes are local SQLite, and
they are gated behind ``dry_run=False`` (the CLI default is dry-run). Re-running is
idempotent — event rows upsert by a stable ``event_index_id``.

Persistence boundary (mirrors ``06_CALENDAR_INGESTION_PLAN.md``): event ID, iCal
UID, web link, subject, organizer, attendees, and location are stored **hashed or
redacted only**; the event body/description and the online-meeting join URL are
never fetched or stored. Private events (``sensitivity in {private, confidential}``)
store minimal metadata only (id hashes, time window, flags) and are flagged
``review_required`` with reason ``private_event``; subject/location/organizer/
attendees are omitted. Project matching and classification are later prompts.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.calendar_readonly_client import ReadOnlyCalendarClient
from hb_assistant.normalize.redaction import hash_value, redact_location, redact_subject

_PAGE_SIZE = 50
_SAMPLE_LIMIT = 10
_PRIVATE_SENSITIVITIES = {"private", "confidential"}
_SAMPLE_KEYS = (
    "event_index_id",
    "start_datetime_utc",
    "end_datetime_utc",
    "is_private",
    "is_cancelled",
    "is_online_meeting",
    "review_required",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _domain(addr: Optional[str]) -> Optional[str]:
    if not addr or "@" not in addr:
        return None
    return addr.split("@", 1)[1].lower()


def _organizer_address(ev: dict[str, Any]) -> Optional[str]:
    return ((ev.get("organizer") or {}).get("emailAddress") or {}).get("address")


def _event_datetime(node: Any) -> Optional[str]:
    if isinstance(node, dict):
        return node.get("dateTime")
    return None


def _subject_token_hashes(subject: Optional[str]) -> Optional[str]:
    """JSON list of hashed subject tokens (>=2 chars). Enables Prompt 05
    project-token matching without ever persisting the raw subject."""
    if not subject:
        return None
    tokens = {t.lower() for t in re.split(r"\W+", subject) if len(t) >= 2}
    hashes = sorted(h for h in (hash_value(t) for t in tokens) if h)
    if not hashes:
        return None
    return json.dumps(hashes)


def normalize_event(
    ev: dict[str, Any], *, source_id: str
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize a raw Graph event into redacted ``upsert_calendar_event_index``
    kwargs + attendee rows. Returns ``(None, [])`` when the event lacks a start/end
    (not indexable). Private events carry minimal metadata only."""
    event_id = ev.get("id")
    graph_event_id_hash = hash_value(event_id)
    start_utc = _event_datetime(ev.get("start"))
    end_utc = _event_datetime(ev.get("end"))
    if not graph_event_id_hash or not start_utc or not end_utc:
        return None, []

    event_index_id = hash_value(f"{source_id}|{graph_event_id_hash}")
    sensitivity = (ev.get("sensitivity") or "").lower()
    is_private = sensitivity in _PRIVATE_SENSITIVITIES
    is_cancelled = bool(ev.get("isCancelled"))

    fields: dict[str, Any] = {
        "event_index_id": event_index_id,
        "source_id": source_id,
        "graph_event_id_hash": graph_event_id_hash,
        "ical_uid_hash": hash_value(ev.get("iCalUId")),
        "series_master_id_hash": hash_value(ev.get("seriesMasterId")),
        "web_link_hash": hash_value(ev.get("webLink")),
        "start_datetime_utc": start_utc,
        "end_datetime_utc": end_utc,
        "timezone": (ev.get("start") or {}).get("timeZone"),
        "is_cancelled": is_cancelled,
        "is_private": is_private,
        "is_online_meeting": bool(ev.get("isOnlineMeeting")),
        "online_meeting_provider": ev.get("onlineMeetingProvider"),
        "has_attachments": bool(ev.get("hasAttachments")),
    }

    attendees: list[dict[str, Any]] = []
    if is_private:
        # Private-event policy: minimal metadata only; flag for review.
        fields["review_required"] = True
        fields["review_reasons_json"] = json.dumps(["private_event"])
        return fields, attendees

    subject = ev.get("subject")
    organizer_addr = _organizer_address(ev)
    location = (ev.get("location") or {}).get("displayName")
    fields.update(
        {
            "subject_hash": hash_value(subject),
            "subject_redacted": redact_subject(subject),
            "subject_token_hashes_json": _subject_token_hashes(subject),
            "organizer_hash": hash_value(organizer_addr),
            "organizer_domain": _domain(organizer_addr),
            "location_hash": hash_value(location),
            "location_redacted": redact_location(location),
            "review_required": False,
        }
    )
    for att in ev.get("attendees") or []:
        addr = ((att.get("emailAddress") or {}).get("address"))
        att_hash = hash_value(addr)
        if not att_hash:
            continue
        attendees.append(
            {
                "attendee_hash": att_hash,
                "attendee_domain": _domain(addr),
                "attendee_role": att.get("type"),
                "response_status": ((att.get("status") or {}).get("response")),
                "review_required": False,
            }
        )
    return fields, attendees


class IndexResult(BaseModel):
    """Outcome of a calendar index run (counts + run id; no subjects/addresses)."""

    source_id: str
    run_id: str
    mode: str  # dry_run | apply
    dry_run: bool
    persisted: bool
    window_start_utc: str
    window_end_utc: str
    lookback_days: int
    lookahead_days: int
    max_items: int
    events_seen: int
    events_indexed: int
    events_private: int
    events_cancelled: int
    events_review_required: int
    status: str  # completed | failed
    sample: list[dict[str, Any]]
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class CalendarEventIndexer:
    """Bounded, read-only calendar event metadata indexer (redacted persistence)."""

    def __init__(
        self, calendar_client: ReadOnlyCalendarClient, store: ConstructionStore
    ) -> None:
        self._calendar = calendar_client
        self._store = store

    def index(
        self,
        *,
        source_id: str,
        mailbox_owner: str = "current_user_hash_only",
        calendar_role: str = "primary",
        policy_id: Optional[str] = None,
        lookback_days: int = 14,
        lookahead_days: int = 30,
        max_items: int = 250,
        dry_run: bool = True,
    ) -> IndexResult:
        now = _utc_now()
        window_start = _iso(now - timedelta(days=lookback_days))
        window_end = _iso(now + timedelta(days=lookahead_days))
        run_id = str(uuid.uuid4())
        mode = "dry_run" if dry_run else "apply"

        events_seen = events_indexed = events_private = 0
        events_cancelled = events_review = 0
        sample: list[dict[str, Any]] = []
        status = "completed"
        error_redacted: Optional[str] = None
        crawl_opened = False

        try:
            me = self._calendar.get_me()
            owner_upn = me.get("userPrincipalName") or me.get("mail")
            if mailbox_owner and mailbox_owner != "current_user_hash_only":
                owner_hash = hash_value(mailbox_owner)
                owner_domain = _domain(mailbox_owner)
            else:
                owner_hash = hash_value(owner_upn)
                owner_domain = _domain(owner_upn)

            if not dry_run:
                self._store.upsert_calendar_source_location(
                    source_id=source_id,
                    mailbox_owner_hash=owner_hash or source_id,
                    mailbox_owner_domain=owner_domain,
                    calendar_role=calendar_role,
                    enabled=True,
                    read_only=True,
                    lookback_days=lookback_days,
                    lookahead_days=lookahead_days,
                    max_items_per_run=max_items,
                    policy_id=policy_id,
                )
                self._store.insert_calendar_crawl_run(
                    run_id=run_id,
                    source_id=source_id,
                    mode=mode,
                    window_start_utc=window_start,
                    window_end_utc=window_end,
                    status="running",
                )
                crawl_opened = True

            events = self._calendar.list_calendar_view(
                start=window_start, end=window_end, top=_PAGE_SIZE, max_items=max_items
            )
            for ev in events:
                events_seen += 1
                fields, attendees = normalize_event(ev, source_id=source_id)
                if fields is None:
                    continue
                if fields["is_private"]:
                    events_private += 1
                if fields["is_cancelled"]:
                    events_cancelled += 1
                if fields.get("review_required"):
                    events_review += 1
                if len(sample) < _SAMPLE_LIMIT:
                    sample.append({k: fields[k] for k in _SAMPLE_KEYS})
                if dry_run:
                    continue
                self._store.upsert_calendar_event_index(**fields)
                for att in attendees:
                    self._store.upsert_calendar_event_attendee(
                        event_index_id=fields["event_index_id"], **att
                    )
                events_indexed += 1
        except Exception as e:  # bounded, sanitized — never raw payloads
            status = "failed"
            error_redacted = f"{type(e).__name__}: {str(e)[:120]}"

        if not dry_run and crawl_opened:
            self._store.complete_calendar_crawl_run(
                run_id=run_id,
                status=status,
                events_seen=events_seen,
                events_indexed=events_indexed,
                events_private=events_private,
                events_cancelled=events_cancelled,
                events_review_required=events_review,
                error_redacted=error_redacted,
            )
            self._store.upsert_calendar_sync_state(
                source_id=source_id,
                last_successful_sync_utc=window_end if status == "completed" else None,
                last_attempted_sync_utc=_iso(now),
                window_start_utc=window_start,
                window_end_utc=window_end,
                last_event_count=events_seen,
                sync_status=status,
                error_redacted=error_redacted,
            )

        return IndexResult(
            source_id=source_id,
            run_id=run_id,
            mode=mode,
            dry_run=dry_run,
            persisted=bool(not dry_run and status == "completed"),
            window_start_utc=window_start,
            window_end_utc=window_end,
            lookback_days=lookback_days,
            lookahead_days=lookahead_days,
            max_items=max_items,
            events_seen=events_seen,
            events_indexed=events_indexed,
            events_private=events_private,
            events_cancelled=events_cancelled,
            events_review_required=events_review,
            status=status,
            sample=sample,
            error_redacted=error_redacted,
        )
