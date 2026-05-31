"""Phase 07B Prompt 04 — bounded calendarView event indexing.

Proves dry-run persists nothing, --apply persists only redacted/hashed metadata
into the V23 tables, private events store minimal metadata and are flagged for
review, the no-raw-body/full-text/writeback CHECK columns stay 0, no raw subject/
organizer/attendee/location/join-URL is ever stored, and re-running is idempotent.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.calendar.event_indexer import (
    CalendarEventIndexer,
    normalize_event,
)
from hb_assistant.construction.store import ConstructionStore

RAW_SUBJECT = "Tropical Job Site Walk 23-435"
RAW_ORG = "pm@hedrickbrothers.com"
RAW_ATT = "super@subcontractor.com"
RAW_LOC = "1200 Banyan Blvd Conference Room"
RAW_JOIN = "https://teams.microsoft.com/l/meetup-join/SECRETJOIN"


class FakeCalendarClient:
    """Records calls; returns canned raw Graph events (normal, private, cancelled)."""

    def __init__(self) -> None:
        self.view_calls: list[tuple[str, str, Optional[int]]] = []

    def get_me(self) -> dict[str, Any]:
        return {"userPrincipalName": "bfetting@hedrickbrothers.com", "mail": "b@x.com"}

    def list_calendar_view(
        self, *, start: str, end: str, top: int = 25, max_items: Optional[int] = None
    ) -> list[dict[str, Any]]:
        self.view_calls.append((start, end, max_items))
        return [
            {
                "id": "EV1",
                "iCalUId": "ICAL1",
                "webLink": "https://outlook/EV1",
                "subject": RAW_SUBJECT,
                "organizer": {"emailAddress": {"address": RAW_ORG}},
                "attendees": [
                    {
                        "emailAddress": {"address": RAW_ATT},
                        "type": "required",
                        "status": {"response": "accepted"},
                    }
                ],
                "start": {"dateTime": "2026-06-01T14:00:00.0000000", "timeZone": "UTC"},
                "end": {"dateTime": "2026-06-01T15:00:00.0000000", "timeZone": "UTC"},
                "location": {"displayName": RAW_LOC},
                "isCancelled": False,
                "sensitivity": "normal",
                "isOnlineMeeting": True,
                "onlineMeetingProvider": "teamsForBusiness",
                "onlineMeeting": {"joinUrl": RAW_JOIN},
                "hasAttachments": True,
            },
            {
                "id": "EV2",
                "subject": "Private 1:1",
                "organizer": {"emailAddress": {"address": RAW_ORG}},
                "attendees": [{"emailAddress": {"address": RAW_ATT}}],
                "start": {"dateTime": "2026-06-02T09:00:00.0", "timeZone": "UTC"},
                "end": {"dateTime": "2026-06-02T09:30:00.0", "timeZone": "UTC"},
                "location": {"displayName": "Private"},
                "isCancelled": False,
                "sensitivity": "private",
                "isOnlineMeeting": False,
            },
            {
                "id": "EV3",
                "subject": "Cancelled Meeting",
                "organizer": {"emailAddress": {"address": RAW_ORG}},
                "start": {"dateTime": "2026-06-03T10:00:00.0", "timeZone": "UTC"},
                "end": {"dateTime": "2026-06-03T11:00:00.0", "timeZone": "UTC"},
                "isCancelled": True,
                "sensitivity": "normal",
                "isOnlineMeeting": False,
            },
        ]


def _indexer(tmp_path: Path) -> tuple[CalendarEventIndexer, str]:
    db = str(tmp_path / "cal.sqlite")
    store = ConstructionStore(db)
    return CalendarEventIndexer(FakeCalendarClient(), store), db  # type: ignore[arg-type]


def test_dry_run_persists_nothing(tmp_path: Path) -> None:
    indexer, db = _indexer(tmp_path)
    result = indexer.index(source_id="primary_calendar", dry_run=True)
    assert result.events_seen == 3
    assert result.events_indexed == 0
    assert result.persisted is False
    assert result.mode == "dry_run"
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_index").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM calendar_crawl_runs").fetchone()[0] == 0
    # Safe sample carries no raw values.
    blob = json.dumps(result.sample)
    for raw in (RAW_SUBJECT, RAW_ORG, RAW_ATT, RAW_LOC, RAW_JOIN):
        assert raw not in blob


def test_apply_persists_redacted_rows_and_counts(tmp_path: Path) -> None:
    indexer, db = _indexer(tmp_path)
    result = indexer.index(source_id="primary_calendar", dry_run=False)
    assert (result.events_seen, result.events_indexed) == (3, 3)
    assert result.events_private == 1
    assert result.events_cancelled == 1
    assert result.events_review_required == 1
    assert result.persisted is True
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_index").fetchone()[0] == 3
    # Only the single non-private event with one attendee yields an attendee row.
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_attendees").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM calendar_crawl_runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM calendar_sync_state").fetchone()[0] == 1
    crawl = conn.execute(
        "SELECT status, events_seen, events_indexed, events_private, events_cancelled,"
        " events_review_required FROM calendar_crawl_runs"
    ).fetchone()
    assert crawl == ("completed", 3, 3, 1, 1, 1)


def test_private_event_is_minimal_and_flagged(tmp_path: Path) -> None:
    indexer, db = _indexer(tmp_path)
    indexer.index(source_id="primary_calendar", dry_run=False)
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT subject_redacted, subject_hash, organizer_hash, location_redacted,"
        " review_required, review_reasons_json FROM calendar_event_index WHERE is_private = 1"
    ).fetchone()
    subj_red, subj_hash, org_hash, loc_red, review, reasons = row
    assert subj_red is None and subj_hash is None
    assert org_hash is None and loc_red is None
    assert review == 1
    assert json.loads(reasons) == ["private_event"]
    # No attendee rows for the private event.
    n = conn.execute(
        "SELECT COUNT(*) FROM calendar_event_attendees a JOIN calendar_event_index e"
        " ON a.event_index_id = e.event_index_id WHERE e.is_private = 1"
    ).fetchone()[0]
    assert n == 0


def test_no_raw_values_persisted(tmp_path: Path) -> None:
    indexer, db = _indexer(tmp_path)
    indexer.index(source_id="primary_calendar", dry_run=False)
    conn = sqlite3.connect(db)
    blob = " ".join(str(r) for r in conn.execute("SELECT * FROM calendar_event_index").fetchall())
    blob += " ".join(
        str(r) for r in conn.execute("SELECT * FROM calendar_event_attendees").fetchall()
    )
    for raw in (RAW_SUBJECT, RAW_ORG, RAW_ATT, RAW_LOC, RAW_JOIN, "teams.microsoft.com"):
        assert raw not in blob, f"raw value leaked: {raw!r}"
    # Redacted subject is the [redacted:...] form for the non-private event.
    red = conn.execute(
        "SELECT subject_redacted FROM calendar_event_index WHERE is_private = 0"
        " AND subject_redacted IS NOT NULL"
    ).fetchone()[0]
    assert red.startswith("[redacted:")


def test_guardrail_check_columns_remain_zero(tmp_path: Path) -> None:
    indexer, db = _indexer(tmp_path)
    indexer.index(source_id="primary_calendar", dry_run=False)
    conn = sqlite3.connect(db)
    g = conn.execute(
        "SELECT SUM(raw_body_persisted), SUM(full_text_persisted),"
        " SUM(external_writeback_performed) FROM calendar_event_index"
    ).fetchone()
    assert g == (0, 0, 0)


def test_apply_is_idempotent(tmp_path: Path) -> None:
    indexer, db = _indexer(tmp_path)
    indexer.index(source_id="primary_calendar", dry_run=False)
    indexer.index(source_id="primary_calendar", dry_run=False)
    conn = sqlite3.connect(db)
    # Stable event_index_id → row count unchanged; crawl receipts accumulate.
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_index").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_attendees").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM calendar_crawl_runs").fetchone()[0] == 2


def test_normalize_event_skips_missing_window() -> None:
    fields, attendees = normalize_event({"id": "X", "subject": "no times"}, source_id="s")
    assert fields is None and attendees == []


def test_normalize_event_omits_join_url_keys() -> None:
    ev = {
        "id": "EV1",
        "subject": "Walk",
        "start": {"dateTime": "2026-06-01T14:00:00Z"},
        "end": {"dateTime": "2026-06-01T15:00:00Z"},
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness",
        "onlineMeeting": {"joinUrl": RAW_JOIN},
    }
    fields, _ = normalize_event(ev, source_id="s")
    assert fields is not None
    # The provider flag is kept; the join URL is never represented.
    assert fields["online_meeting_provider"] == "teamsForBusiness"
    assert "online_meeting_link" not in fields
    assert RAW_JOIN not in json.dumps(fields)
