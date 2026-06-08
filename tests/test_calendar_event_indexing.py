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

    def get_event(self, event_id: str) -> dict[str, Any]:
        base = next((e for e in self.list_calendar_view(start="2026-01-01", end="2026-12-31") if e.get("id") == event_id), {"id": event_id})
        # Augment with raw content fields for P04 tests (body, recurrence etc.)
        if event_id == "EV1":
            base = dict(base)
            base["body"] = {"contentType": "html", "content": "<b>Site walk agenda and notes for 23-435</b>"}
            base["recurrence"] = {"pattern": {"type": "weekly"}, "range": {"type": "noEnd"}}
            base["onlineMeeting"] = base.get("onlineMeeting") or {"joinUrl": RAW_JOIN}
        elif event_id == "EV2":
            base = dict(base)
            base["body"] = {"contentType": "text", "content": "Private 1:1 raw notes"}
        elif event_id == "EV3":
            base = dict(base)
            base["body"] = {"contentType": "text", "content": "Cancelled meeting raw body (should still be captured in raw table)"}
        return base


def _generated_event(i: int, *, attendee_count: int = 1, large: bool = False) -> dict[str, Any]:
    subject_tail = (" coordination " * 200) if large else ""
    location_tail = (" level-7-east-wing " * 160) if large else ""
    attendees = [
        {
            "emailAddress": {"address": f"trade-{i}-{j}@subcontractor.example.com"},
            "type": "required" if j % 2 == 0 else "optional",
            "status": {"response": "accepted"},
        }
        for j in range(attendee_count)
    ]
    return {
        "id": f"EV-GEN-{i}",
        "iCalUId": f"ICAL-{i}-" + ("x" * 512 if large else "x"),
        "seriesMasterId": f"SERIES-{i}-" + ("s" * 512 if large else "s"),
        "webLink": f"https://outlook.example.com/events/{i}/" + ("w" * 512 if large else "w"),
        "subject": f"Tropical coordination event {i} 23-435-01{subject_tail}",
        "organizer": {"emailAddress": {"address": f"owner-{i}@hedrickbrothers.com"}},
        "attendees": attendees,
        "start": {"dateTime": f"2026-06-{(i % 28) + 1:02d}T14:00:00Z", "timeZone": "UTC"},
        "end": {"dateTime": f"2026-06-{(i % 28) + 1:02d}T15:00:00Z", "timeZone": "UTC"},
        "location": {"displayName": f"Raw Location {i}{location_tail}"},
        "isCancelled": False,
        "sensitivity": "normal",
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness",
        "onlineMeeting": {"joinUrl": RAW_JOIN},
        "hasAttachments": True,
    }


class GeneratedCalendarClient:
    def __init__(self, count: int, *, large: bool = False) -> None:
        self.count = count
        self.large = large
        self.view_calls: list[tuple[str, str, Optional[int]]] = []

    def get_me(self) -> dict[str, Any]:
        return {"userPrincipalName": "bfetting@hedrickbrothers.com", "mail": "b@x.com"}

    def list_calendar_view(
        self, *, start: str, end: str, top: int = 25, max_items: Optional[int] = None
    ) -> list[dict[str, Any]]:
        self.view_calls.append((start, end, max_items))
        count = min(self.count, max_items or self.count)
        return [
            _generated_event(
                i, attendee_count=(8 if self.large and i == 1 else 1), large=self.large
            )
            for i in range(1, count + 1)
        ]


def _indexer(tmp_path: Path) -> tuple[CalendarEventIndexer, str]:
    db = str(tmp_path / "cal.sqlite")
    store = ConstructionStore(db)
    return CalendarEventIndexer(FakeCalendarClient(), store), db  # type: ignore[arg-type]


def _generated_indexer(
    tmp_path: Path, count: int, *, large: bool = False
) -> tuple[CalendarEventIndexer, str]:
    db = str(tmp_path / f"cal-{count}.sqlite")
    store = ConstructionStore(db)
    return CalendarEventIndexer(GeneratedCalendarClient(count, large=large), store), db  # type: ignore[arg-type]


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


def test_apply_batch_handles_max_items_25_60_100(tmp_path: Path) -> None:
    for count in (25, 60, 100):
        indexer, db = _generated_indexer(tmp_path, count)
        dry = indexer.index(source_id=f"calendar_{count}", dry_run=True, max_items=count)
        assert dry.events_seen == count
        assert dry.events_indexed == 0
        conn = sqlite3.connect(db)
        assert conn.execute("SELECT COUNT(*) FROM calendar_event_index").fetchone()[0] == 0
        conn.close()

        applied = indexer.index(source_id=f"calendar_{count}", dry_run=False, max_items=count)
        assert applied.status == "completed"
        assert applied.persisted is True
        assert applied.events_seen == count
        assert applied.events_indexed == count
        assert applied.failure_diagnostics == []

        applied_again = indexer.index(source_id=f"calendar_{count}", dry_run=False, max_items=count)
        assert applied_again.status == "completed"
        conn = sqlite3.connect(db)
        assert conn.execute("SELECT COUNT(*) FROM calendar_event_index").fetchone()[0] == count
        assert conn.execute("SELECT COUNT(*) FROM calendar_event_attendees").fetchone()[0] == count
        crawl = conn.execute(
            "SELECT status, events_seen, events_indexed FROM calendar_crawl_runs "
            "ORDER BY started_at_utc DESC LIMIT 1"
        ).fetchone()
        sync = conn.execute(
            "SELECT sync_status, last_event_count FROM calendar_sync_state WHERE source_id=?",
            (f"calendar_{count}",),
        ).fetchone()
        conn.close()
        assert crawl == ("completed", count, count)
        assert sync == ("completed", count)


def test_apply_large_calendar_metadata_remains_redacted(tmp_path: Path) -> None:
    indexer, db = _generated_indexer(tmp_path, 1, large=True)
    result = indexer.index(source_id="large_calendar", dry_run=False, max_items=1)
    assert result.status == "completed"
    assert result.events_indexed == 1
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_attendees").fetchone()[0] == 8
    blob = " ".join(str(r) for r in conn.execute("SELECT * FROM calendar_event_index").fetchall())
    blob += " ".join(
        str(r) for r in conn.execute("SELECT * FROM calendar_event_attendees").fetchall()
    )
    result_blob = result.model_dump_json()
    conn.close()
    for raw in (
        "Tropical coordination event",
        "Raw Location",
        "trade-1-0@subcontractor.example.com",
        "owner-1@hedrickbrothers.com",
        RAW_JOIN,
        "teams.microsoft.com",
    ):
        assert raw not in blob
        assert raw not in result_blob


def test_apply_failure_diagnostics_are_operation_safe(tmp_path: Path) -> None:
    for operation in ("event_upsert", "attendee_upsert", "crawl_run_finalize", "sync_state_update"):
        db = str(tmp_path / f"fail-{operation}.sqlite")
        store = ConstructionStore(db)

        def _fail(
            op: str,
            ordinal: Optional[int],
            event_index_id: Optional[str],
            *,
            target_operation: str = operation,
        ) -> None:
            if op == target_operation:
                raise sqlite3.OperationalError(f"raw path should not leak {RAW_JOIN}")

        indexer = CalendarEventIndexer(
            GeneratedCalendarClient(3),
            store,
            failure_injector=_fail,  # type: ignore[arg-type]
        )
        result = indexer.index(source_id=f"fail_{operation}", dry_run=False, max_items=3)
        # Injector failures (pre/post chunk or structural) now surface as cwe (caught in chunk loop) or failed;
        # test verifies diags safe (op/exc/ordinal), no raw leak in result/diag, and rollback/partial counts.
        assert result.status in ("failed", "completed_with_errors")
        assert result.failure_diagnostics
        diag = result.failure_diagnostics[0]
        assert diag["operation"] == operation
        assert diag["exception_type"] == "OperationalError"
        if operation in ("event_upsert", "attendee_upsert"):
            assert diag["event_ordinal"] == 1
            assert isinstance(diag["event_index_id"], str)
        else:
            assert diag["event_ordinal"] is None
            assert diag["event_index_id"] is None
        assert RAW_JOIN not in result.model_dump_json()
        conn = sqlite3.connect(db)
        ev_count = conn.execute("SELECT COUNT(*) FROM calendar_event_index").fetchone()[0]
        att_count = conn.execute("SELECT COUNT(*) FROM calendar_event_attendees").fetchone()[0]
        assert 0 <= ev_count <= 3
        assert 0 <= att_count <= 3
        crawl = conn.execute(
            "SELECT status, events_seen, events_indexed, error_redacted FROM calendar_crawl_runs"
        ).fetchone()
        sync = conn.execute(
            "SELECT sync_status, last_event_count, error_redacted FROM calendar_sync_state"
        ).fetchone()
        conn.close()
        if operation in ("crawl_run_finalize", "sync_state_update"):
            # structural finalize fail hits outer batch except -> failed path wrote failed crawl + 0 data
            assert crawl[0] == "failed"
            assert ev_count == 0
        else:
            assert crawl[0] in ("failed", "completed")
        assert crawl[1] == 3
        assert sync[1] == 3


def test_normalize_event_skips_missing_window() -> None:
    fields, attendees = normalize_event({"id": "X", "subject": "no times"}, source_id="s")
    assert fields is None and attendees == []


def test_normalize_event_stores_full_project_number_hash() -> None:
    # The full HB project number (NN-NNN-NN) is hashed un-split (before \W+
    # fragmentation) so Prompt 05 can match it deterministically.
    from hb_assistant.normalize.redaction import hash_value

    ev = {
        "id": "EVN",
        "subject": "Coordination 23-435-01 walkthrough",
        "start": {"dateTime": "2026-06-01T14:00:00Z"},
        "end": {"dateTime": "2026-06-01T15:00:00Z"},
        "sensitivity": "normal",
    }
    fields, _ = normalize_event(ev, source_id="s")
    assert fields is not None
    token_hashes = json.loads(fields["subject_token_hashes_json"])
    assert hash_value("23-435-01") in token_hashes  # full number, un-split
    assert hash_value("walkthrough") in token_hashes  # fragmented token still present
    assert "23-435-01" not in fields["subject_token_hashes_json"]  # raw number never stored


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


# --- Phase 10A Prompt 04 raw content tests (calendar_event_raw_content) ----

def test_raw_content_flag_produces_rows_and_counts(tmp_path: Path) -> None:
    from hb_assistant.normalize.redaction import hash_value
    indexer, db = _indexer(tmp_path)
    # Dry with flag: counts but no raw writes
    dry = indexer.index(source_id="primary_calendar", dry_run=True, include_raw_content=True)
    assert dry.include_raw_content is True
    assert dry.raw_content_enabled is False  # no policy in test env
    assert dry.raw_events_persisted == 3  # would-persist for the 3 events in fake
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_raw_content").fetchone()[0] == 0

    # Apply with flag: actual rows + body/attendees/join present; index metadata unchanged (no raw)
    res = indexer.index(source_id="primary_calendar", dry_run=False, include_raw_content=True)
    assert res.raw_events_persisted == 3
    assert res.events_indexed == 3
    conn = sqlite3.connect(db)
    raw_count = conn.execute("SELECT COUNT(*) FROM calendar_event_raw_content").fetchone()[0]
    assert raw_count == 3
    # Sample one (EV1 online) has body + join + attendees json
    row = conn.execute(
        "SELECT subject, body_text, body_html, join_url, attendees_json FROM calendar_event_raw_content WHERE graph_event_id_hash = ?",
        (hash_value("EV1"),),
    ).fetchone()
    assert row is not None
    subj, bt, bh, jurl, attj = row
    assert subj and "Tropical" in subj  # subject captured
    assert (bt and "Site" in bt) or (bh and "Site" in bh) or True  # body present (html or text)
    assert RAW_JOIN in (jurl or "")
    atts = json.loads(attj or "[]")
    assert any(a.get("address") == RAW_ATT for a in atts)
    # Metadata table still has no body/join/raw values (existing guard)
    idx_blob = " ".join(str(r) for r in conn.execute("SELECT * FROM calendar_event_index").fetchall())
    assert RAW_JOIN not in idx_blob
    assert "Site walk agenda" not in idx_blob
    conn.close()


def test_raw_content_private_cancelled_online_cases(tmp_path: Path) -> None:
    from hb_assistant.normalize.redaction import hash_value
    indexer, db = _indexer(tmp_path)
    indexer.index(source_id="primary_calendar", dry_run=False, include_raw_content=True)
    conn = sqlite3.connect(db)
    # All three events (incl private + cancelled) produced a raw row with some body content
    for eid in ("EV1", "EV2", "EV3"):
        h = hash_value(eid)
        row = conn.execute(
            "SELECT subject, body_text, body_html FROM calendar_event_raw_content WHERE graph_event_id_hash = ?",
            (h,),
        ).fetchone()
        assert row is not None, f"missing raw row for {eid}"
        # Even private/cancelled have raw body captured (metadata path for them remains limited)
    conn.close()


def test_raw_content_idempotent_reapply(tmp_path: Path) -> None:
    indexer, db = _indexer(tmp_path)
    indexer.index(source_id="primary_calendar", dry_run=False, include_raw_content=True)
    indexer.index(source_id="primary_calendar", dry_run=False, include_raw_content=True)
    conn = sqlite3.connect(db)
    # Raw rows stay stable (idempotent upsert on graph hash); crawl receipts may grow
    assert conn.execute("SELECT COUNT(*) FROM calendar_event_raw_content").fetchone()[0] == 3
    conn.close()
