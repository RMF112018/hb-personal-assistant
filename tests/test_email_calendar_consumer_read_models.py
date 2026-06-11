"""Pass 2 — consumer rewiring to the structured projection layer with source-quality precedence.

Proves: the read model selects the structured projection ahead of raw-landing/legacy/metadata;
a lower-quality row can never downgrade consumer context; email/calendar endpoints expose the
selected source-tier; meeting prep + model-context packets + retrieval use the structured layer
and emit no raw body / join URL; raw reads write access-audit events; and the CLI apply path is
safe (dry-run default, refuses --apply without --db).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.email_calendar import projection_engine as eng
from hb_assistant.construction.email_calendar import read_models as rm
from hb_assistant.construction.email_calendar.redaction import no_raw_leak_scan
from hb_assistant.construction.store.repositories import ConstructionStore

BODY = "P2_BODY_SENTINEL"
AGENDA = "P2_AGENDA_SENTINEL"
JOIN = "https://teams.microsoft.com/l/P2_JOIN_SENTINEL"


def _store(tmp_path: Path) -> ConstructionStore:
    return ConstructionStore(db_path=str(tmp_path / "ec.sqlite"))


def _seed_and_project(store: ConstructionStore) -> None:
    store.upsert_email_message_raw_content(
        raw_email_id="raw:m1",
        message_id_hash="mh1",
        conversation_id_hash="ch1",
        project_key="proj",
        subject="Kickoff",
        body_text=BODY,
        from_address="a@hb.com",
        to_recipients_json=json.dumps([{"name": "Bob", "address": "bob@x.com"}]),
        source_quality="graph_full_body",
    )
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1",
        graph_event_id_hash="g1",
        event_index_id="eidx1",
        project_key="proj",
        subject="Weekly",
        body_text=AGENDA,
        location_display="Room 1",
        organizer_name="Org",
        organizer_email="org@hb.com",
        attendees_json=json.dumps(
            [{"type": "required", "status": "accepted", "name": "B", "address": "b@hb.com"}]
        ),
        join_url=JOIN,
        start_datetime_utc="2026-06-10T15:00:00Z",
        source_quality="graph_full_event_body",
    )
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)


# --- read model precedence ------------------------------------------------------


def test_read_model_selects_structured_ahead_of_raw(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_and_project(store)
    ctx = rm.select_email_message_context(store, message_id_hash="mh1")
    assert ctx.selected_source == rm.TIER_STRUCTURED_FULL
    assert ctx.source_quality == "graph_full_body"
    assert ctx.recipient_count == 2 and len(ctx.recipients) == 2
    ev = rm.select_event_context(store, event_index_id="eidx1")
    assert ev.selected_source == rm.TIER_STRUCTURED_FULL
    assert ev.has_join_url is True and ev.attendee_count == 1


def test_read_model_falls_back_to_raw_only_when_no_structured(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # seed raw but DO NOT project
    store.upsert_email_message_raw_content(
        raw_email_id="raw:m9",
        message_id_hash="mh9",
        subject="x",
        body_text=BODY,
        source_quality="graph_full_body",
    )
    ctx = rm.select_email_message_context(store, message_id_hash="mh9")
    assert ctx.selected_source == rm.TIER_RAW_LANDING
    # once projected, structured wins (never a silent legacy/raw pick when structured exists)
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    ctx2 = rm.select_email_message_context(store, message_id_hash="mh9")
    assert ctx2.selected_source == rm.TIER_STRUCTURED_FULL


def test_lower_quality_cannot_downgrade_consumer_context(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_and_project(store)
    # downgrade the raw row + reproject: structured stays graph_full_body, consumer keeps full
    conn = sqlite3.connect(store._db_path)
    conn.execute(
        "UPDATE email_message_raw_content SET source_quality='metadata_only', body_text=NULL "
        "WHERE raw_email_id='raw:m1'"
    )
    conn.commit()
    conn.close()
    eng.reprocess(db_path=store._db_path, apply=True, mode=eng.MODE_ENFORCE)
    ctx = rm.select_email_message_context(store, message_id_hash="mh1")
    assert ctx.selected_source == rm.TIER_STRUCTURED_FULL
    assert ctx.source_quality == "graph_full_body"


def test_read_model_objects_carry_no_body_or_join_url(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_and_project(store)
    ctx = rm.select_email_message_context(store, message_id_hash="mh1")
    ev = rm.select_event_context(store, event_index_id="eidx1")
    blob = json.dumps([ctx.__dict__, ev.__dict__])
    assert BODY not in blob and AGENDA not in blob and "P2_JOIN_SENTINEL" not in blob


def test_load_body_returns_local_private_and_audits(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_and_project(store)
    before = (
        sqlite3.connect(store._db_path)
        .execute("SELECT COUNT(*) FROM raw_content_access_events")
        .fetchone()[0]
    )
    ctx = rm.select_email_message_context(store, message_id_hash="mh1")
    body = ctx.load_body(store, purpose="test")
    after = (
        sqlite3.connect(store._db_path)
        .execute("SELECT COUNT(*) FROM raw_content_access_events")
        .fetchone()[0]
    )
    assert body["body_text"] == BODY
    assert after == before + 1  # raw read audited


# --- endpoints ------------------------------------------------------------------


def test_email_endpoint_exposes_selected_source(tmp_path: Path, monkeypatch) -> None:
    from hb_assistant.construction.email import endpoints as eep

    store = _store(tmp_path)
    _seed_and_project(store)
    monkeypatch.setattr(eep, "_resolve_include_raw", lambda **k: True)
    # a metadata message row whose hash matches our structured row
    monkeypatch.setattr(store, "list_email_messages", lambda **k: [{"message_id": "mid1"}])
    monkeypatch.setattr("hb_assistant.construction.email.endpoints.hash_value", lambda v: "mh1")
    rows = eep.list_email_messages(store=store)
    assert rows[0]["_selected_source"] == rm.TIER_STRUCTURED_FULL
    assert rows[0]["source_quality"] == "graph_full_body"


def test_calendar_endpoint_exposes_selected_source(tmp_path: Path, monkeypatch) -> None:
    from hb_assistant.construction.calendar import endpoints as cep

    store = _store(tmp_path)
    _seed_and_project(store)
    monkeypatch.setattr(cep, "_resolve_include_raw", lambda **k: True)
    monkeypatch.setattr(
        store,
        "list_calendar_event_index",
        lambda **k: [{"event_index_id": "eidx1", "is_cancelled": 0}],
    )
    rows = cep.list_calendar_events(store=store)
    assert rows[0]["_selected_source"] == rm.TIER_STRUCTURED_FULL
    assert rows[0]["source_quality"] == "graph_full_event_body"


# --- meeting prep ---------------------------------------------------------------


def test_meeting_prep_uses_structured_and_no_leak(tmp_path: Path) -> None:
    import datetime as dt

    from hb_assistant.construction.meeting_prep.brief_builder import MeetingPrepBriefBuilder

    store = _store(tmp_path)
    _seed_and_project(store)
    # provide a metadata index row for the matched event
    store.list_calendar_event_index = lambda **k: [  # type: ignore[method-assign]
        {
            "event_index_id": "eidx1",
            "project_key": "proj",
            "is_cancelled": 0,
            "start_datetime_utc": "2026-06-10T15:00:00Z",
        }
    ]
    mb = MeetingPrepBriefBuilder(store=store)
    sec = mb._section_meeting_context("proj", 30, dt.datetime(2026, 6, 9, tzinfo=dt.timezone.utc))
    blob = json.dumps(sec)
    assert "matched_event_details" in sec["section_redacted"]
    assert AGENDA not in blob and "P2_JOIN_SENTINEL" not in blob
    assert "structured_full" in sec["section_redacted"]  # structured tier recorded


# --- model context --------------------------------------------------------------


def test_model_context_packet_records_structured(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.local_ai.raw_context import (
        build_raw_calendar_context_packet,
    )

    store = _store(tmp_path)
    _seed_and_project(store)
    pkt = build_raw_calendar_context_packet(project_key="proj", store=store)
    assert pkt.get("structured_projection_preferred") is True
    assert pkt.get("source_quality_distribution", {}).get("structured_full") == 1


# --- relationship extraction + retrieval ---------------------------------------


def test_relationships_tagged_structured(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.local_ai.relationship_scoring import (
        find_email_calendar_relationships,
    )

    store = _store(tmp_path)
    # seed a thread raw row + project so structured thread exists
    store.upsert_email_thread_raw_context(
        raw_thread_context_id="rawctx:t1",
        thread_ref="ch1",
        conversation_id_hash="ch1",
        project_key="proj",
        message_count=1,
        thread_subject="Weekly",
        messages_json=json.dumps(
            [
                {
                    "subject": "Weekly",
                    "from_address": "org@hb.com",
                    "received_at": "2026-06-10T14:00:00Z",
                    "body_text": BODY,
                }
            ]
        ),
    )
    _seed_and_project(store)
    rels = find_email_calendar_relationships(store=store, project_key="proj", min_confidence=0.0)
    assert rels, "expected at least one scored relationship"
    assert "thread_source_quality" in rels[0] and "structured_backed" in rels[0]


def test_retrieval_structured_is_redacted(tmp_path: Path) -> None:
    from hb_assistant.retrieval.retriever import retrieve_email_calendar_structured

    store = _store(tmp_path)
    _seed_and_project(store)
    hits = retrieve_email_calendar_structured(store, query="weekly", project_key="proj")
    blob = json.dumps(hits)
    assert hits and BODY not in blob and AGENDA not in blob
    # subject is hashed, not raw
    assert all("subject_ref" in h and h.get("source_quality") for h in hits)


# --- CLI safety -----------------------------------------------------------------


def test_cli_reprocess_refuses_apply_without_db() -> None:
    from typer.testing import CliRunner

    from hb_assistant.cli.email_calendar import app

    res = CliRunner().invoke(app, ["raw", "projection-reprocess", "--apply"])
    assert res.exit_code == 2
    assert "refused_apply_without_db" in res.stdout


def test_cli_reprocess_dry_run_default_writes_nothing(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from hb_assistant.cli.email_calendar import app

    store = _store(tmp_path)
    store.upsert_email_message_raw_content(
        raw_email_id="raw:m1",
        message_id_hash="mh1",
        subject="s",
        body_text=BODY,
        source_quality="graph_full_body",
    )
    res = CliRunner().invoke(app, ["raw", "projection-reprocess", "--db", store._db_path])
    assert res.exit_code == 0
    assert '"mode": "dry_run"' in res.stdout
    n = (
        sqlite3.connect(store._db_path)
        .execute("SELECT COUNT(*) FROM email_raw_message_structured")
        .fetchone()[0]
    )
    assert n == 0


def test_no_leak_scan_zero_on_clean_evidence(tmp_path: Path) -> None:
    p = tmp_path / "evidence.md"
    p.write_text("rows=117 unmapped_primary=0 source_quality=graph_full_event_body verdict=ok")
    res = no_raw_leak_scan([tmp_path], sentinels=[BODY, AGENDA])
    assert res["ok"] is True and res["unsafe_finding_count"] == 0
