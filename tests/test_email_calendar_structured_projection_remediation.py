"""Final structured projection of email/calendar raw content (Pass 1, Prompts 04B-04D).

Proves every available raw row projects into final structured parent + child tables: full
bodies stay local-private in the raw tables (the structured row carries availability flags +
a raw-row link, never a duplicated body), nested arrays (recipients/attachments/attendees/
recurrence/locations/thread-messages) populate child tables, source-quality precedence
prevents downgrades, projection is idempotent, run/coverage receipts are written, and a
source family with no raw rows is honestly reported as ``no_raw_rows_available_in_current_copy``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.email_calendar import projection_engine as eng
from hb_assistant.construction.store.repositories import ConstructionStore

BODY = "STRUCT_BODY_SENTINEL"
AGENDA = "STRUCT_AGENDA_SENTINEL"
JOIN = "https://teams.microsoft.com/l/STRUCT_JOIN_SENTINEL"


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "ec.sqlite"))


def _conn(store: ConstructionStore) -> sqlite3.Connection:
    conn = sqlite3.connect(store._db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_email(store: ConstructionStore) -> None:
    store.upsert_email_message_raw_content(
        raw_email_id="raw:m1",
        message_id_hash="mh1",
        conversation_id_hash="ch1",
        project_key="proj-a",
        subject="Kickoff",
        body_text=BODY,
        body_html=f"<p>{BODY}</p>",
        from_name="Alice",
        from_address="alice@hb.com",
        to_recipients_json=json.dumps([{"name": "Bob", "address": "bob@sub.com"}]),
        cc_recipients_json=json.dumps([{"name": "Cara", "address": "cara@hb.com"}]),
        has_attachments=1,
        attachment_metadata_json=json.dumps(
            [
                {
                    "name": "plan.pdf",
                    "contentType": "application/pdf",
                    "size": 9,
                    "isInline": False,
                    "id": "a1",
                }
            ]
        ),
        source_quality="graph_full_body",
        raw_sidecar_json=json.dumps({"importance": "high", "categories": ["Ops"]}),
    )


def _seed_thread(store: ConstructionStore) -> None:
    store.upsert_email_thread_raw_context(
        raw_thread_context_id="rawctx:t1",
        thread_ref="ch1",
        conversation_id_hash="ch1",
        project_key="proj-a",
        message_count=2,
        participant_count=3,
        thread_subject="Kickoff",
        messages_json=json.dumps(
            [
                {
                    "subject": "Kickoff",
                    "body_text": BODY,
                    "from_name": "Alice",
                    "from_address": "alice@hb.com",
                    "received_at": "2026-06-01T00:00:00Z",
                },
                {
                    "subject": "RE: Kickoff",
                    "body_text": "reply",
                    "from_name": "Bob",
                    "from_address": "bob@sub.com",
                    "received_at": "2026-06-02T00:00:00Z",
                },
            ]
        ),
        source_refs_json=json.dumps(["src-1", "src-2"]),
    )


def _seed_calendar(store: ConstructionStore) -> None:
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="g1",
        event_index_id="eidx1",
        project_key="proj-a",
        subject="Weekly",
        body_text=AGENDA,
        location_display="Room 1",
        organizer_name="Org",
        organizer_email="org@hb.com",
        attendees_json=json.dumps(
            [
                {"type": "required", "status": "accepted", "name": "Bob", "address": "bob@hb.com"},
                {"type": "optional", "status": "none", "name": "Cara", "address": "cara@x.com"},
            ]
        ),
        online_meeting_provider="teamsForBusiness",
        join_url=JOIN,
        recurrence_json=json.dumps(
            {
                "pattern": {"type": "weekly", "interval": 1, "daysOfWeek": ["monday"]},
                "range": {"type": "endDate", "startDate": "2026-01-01", "endDate": "2026-12-31"},
            }
        ),
        start_datetime_utc="2026-06-10T15:00:00Z",
        end_datetime_utc="2026-06-10T15:30:00Z",
        source_quality="graph_full_event_body",
        raw_sidecar_json=json.dumps(
            {
                "isAllDay": False,
                "categories": ["Ops"],
                "createdDateTime": "2026-05-01T00:00:00Z",
                "locations": [
                    {
                        "displayName": "Room 1",
                        "locationType": "conferenceRoom",
                        "locationUri": "room1@hb.com",
                    }
                ],
            }
        ),
    )


def test_email_projects_to_parent_and_children(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    rep = eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    assert rep["ok"]
    conn = _conn(store)
    parent = conn.execute("SELECT * FROM email_raw_message_structured").fetchone()
    assert parent["raw_email_id"] == "raw:m1"
    assert parent["raw_row_id"] == "raw:m1"  # raw linkage
    assert parent["source_quality"] == "graph_full_body"
    assert parent["body_text_available"] == 1 and parent["body_text_chars"] == len(BODY)
    assert parent["recipient_count"] == 3 and parent["attachment_count"] == 1
    # body is NOT duplicated into the structured row
    assert "body_text" not in set(parent.keys())
    roles = [
        r["role"]
        for r in conn.execute(
            "SELECT role FROM email_raw_message_recipients_structured ORDER BY child_index"
        )
    ]
    assert roles == ["from", "to", "cc"]
    att = conn.execute(
        "SELECT name, content_type FROM email_raw_message_attachments_structured"
    ).fetchone()
    assert att["name"] == "plan.pdf" and att["content_type"] == "application/pdf"
    # lossless sidecar preserved on the parent
    assert "Ops" in (parent["payload_sidecar_json"] or "")


def test_thread_projects_from_persisted_rows(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_thread(store)
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    conn = _conn(store)
    parent = conn.execute("SELECT * FROM email_raw_thread_structured").fetchone()
    assert parent["message_count"] == 2 and parent["has_full_body"] == 1
    msgs = conn.execute(
        "SELECT body_text_available FROM email_raw_thread_messages_structured ORDER BY child_index"
    ).fetchall()
    assert len(msgs) == 2 and msgs[0]["body_text_available"] == 1
    assert "src-1" in (parent["source_refs_sidecar_json"] or "")


def test_calendar_projects_attendees_recurrence_locations(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_calendar(store)
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    conn = _conn(store)
    parent = conn.execute("SELECT * FROM calendar_raw_event_structured").fetchone()
    assert parent["has_join_url"] == 1 and parent["join_url_policy"] == "local_db_only"
    assert parent["attendee_count"] == 2 and parent["has_recurrence"] == 1
    # the join URL value is never in the structured parent row
    assert "STRUCT_JOIN_SENTINEL" not in json.dumps(dict(parent))
    assert (
        len(conn.execute("SELECT 1 FROM calendar_raw_event_attendees_structured").fetchall()) == 2
    )
    rec = conn.execute(
        "SELECT pattern_type, range_type, range_end FROM calendar_raw_event_recurrence_structured"
    ).fetchone()
    assert rec["pattern_type"] == "weekly" and rec["range_end"] == "2026-12-31"
    loc = conn.execute(
        "SELECT display_name, location_type FROM calendar_raw_event_locations_structured"
    ).fetchone()
    assert loc["display_name"] == "Room 1" and loc["location_type"] == "conferenceRoom"


def test_projection_is_idempotent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    _seed_calendar(store)
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    conn = _conn(store)
    assert conn.execute("SELECT COUNT(*) FROM email_raw_message_structured").fetchone()[0] == 1
    # from + to + cc = 3 recipient rows; idempotent re-run keeps exactly 3
    assert (
        conn.execute("SELECT COUNT(*) FROM email_raw_message_recipients_structured").fetchone()[0]
        == 3
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM calendar_raw_event_attendees_structured").fetchone()[0]
        == 2
    )


def test_projection_downgrade_prevention(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    # Force the structured row's linked raw row to a lower quality and reproject.
    conn = sqlite3.connect(store._db_path)
    conn.execute(
        "UPDATE email_message_raw_content SET source_quality='metadata_only', body_text=NULL "
        "WHERE raw_email_id='raw:m1'"
    )
    conn.commit()
    conn.close()
    rep = eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    em = next(f for f in rep["families"] if f["source_family"] == "email_message")
    assert em["skipped_higher_quality"] == 1
    row = (
        _conn(store)
        .execute("SELECT source_quality, body_text_available FROM email_raw_message_structured")
        .fetchone()
    )
    assert row["source_quality"] == "graph_full_body" and row["body_text_available"] == 1


def test_run_and_coverage_receipts_written(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    _seed_calendar(store)
    rep = eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    conn = _conn(store)
    runs = conn.execute(
        "SELECT source_family, projected_parent_rows, status FROM email_calendar_projection_runs"
    ).fetchall()
    assert {r["source_family"] for r in runs} >= {"email_message", "calendar_event"}
    cov = conn.execute(
        "SELECT unmapped_primary_business_fields, unmapped_nested_business_fields, status "
        "FROM email_calendar_projection_coverage WHERE source_family='calendar_event'"
    ).fetchone()
    assert cov["unmapped_primary_business_fields"] == 0
    assert cov["unmapped_nested_business_fields"] == 0
    assert rep["ok"]


def test_no_raw_rows_family_marked_honestly(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)  # only email seeded; calendar + thread have no raw rows
    rep = eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    cal = next(f for f in rep["families"] if f["source_family"] == "calendar_event")
    assert cal["status"] == "no_raw_rows_available_in_current_copy"


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_email(store)
    rep = eng.reprocess(db_path=store._db_path, apply=False, mode=eng.MODE_ENFORCE)
    assert rep["mode"] == "dry_run"
    conn = _conn(store)
    assert conn.execute("SELECT COUNT(*) FROM email_raw_message_structured").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM email_calendar_projection_runs").fetchone()[0] == 0
