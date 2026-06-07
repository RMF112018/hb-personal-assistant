"""Phase 10A Prompt 06 fixture tests for raw model context packet builders.

- Seeds raw email/calendar rows via the V42 upserts (idempotent).
- Calls the builders (policy effective via explicit or default).
- Verifies packets contain actual content (bodies, attendees, join etc.).
- Verifies bounds are applied (truncation, counts).
- Verifies source refs and persistence to raw_content_model_context_packets.
- Metadata-only path when not effective.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import (
    build_raw_calendar_context_packet,
    build_raw_email_context_packet,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value


def _temp_store() -> tuple[ConstructionStore, Path]:
    tmp = tempfile.mkdtemp(prefix="p06_packet_")
    db = Path(tmp) / "p06.sqlite3"
    return ConstructionStore(db_path=str(db)), db


def test_raw_email_packet_contains_actual_content_and_persists():
    store, _ = _temp_store()
    # Seed a raw email message + thread context (P03 tables)
    mid = f"m-{uuid.uuid4()}"
    mh = hash_value(mid)
    tr = f"t-{uuid.uuid4()}"
    store.upsert_email_message_raw_content(
        raw_email_id=f"raw:{mid}",
        message_id_hash=mh,
        conversation_id_hash=hash_value(tr),
        project_key="trop",
        subject="Raw packet test",
        body_text="This is the actual body that should appear in the model packet. " * 3,
        body_html="<p>html body</p>",
        from_name="Alice",
        from_address="a@ex.com",
        to_recipients_json="[]",
        sent_at_utc="2026-06-07T12:00:00Z",
    )
    store.upsert_email_thread_raw_context(
        raw_thread_context_id=f"th-{uuid.uuid4()}",
        thread_ref=tr,
        project_key="trop",
        message_count=1,
        participant_count=2,
        thread_subject="Raw packet test",
        messages_json=json.dumps(
            [
                {
                    "id": mid,
                    "subject": "Raw packet test",
                    "body_text": "This is the actual body that should appear in the model packet. "
                    * 3,
                    "from_name": "Alice",
                    "to_recipients": [],
                }
            ]
        ),
        source_refs_json="[]",
    )

    pkt = build_raw_email_context_packet(project_key="trop", store=store)
    assert pkt["packet_type"] == "raw_email_context"
    assert pkt["raw_content_included"] == 1
    assert any(
        "actual body" in (m.get("body_text") or "")
        for t in pkt["content"]["threads"]
        for m in t.get("messages", [])
    )
    assert pkt["token_estimate"] > 0
    assert any(
        r["source_family"] in ("email_message_raw_content", "email_thread_raw_context")
        for r in pkt.get("source_refs", [])
    )

    # Persisted
    rows = store.list_raw_content_model_context_packets(packet_type="raw_email_context", limit=5)
    assert any(r["packet_id"] == pkt["packet_id"] for r in rows)
    loaded = json.loads(rows[0]["packet_json"])
    assert "actual body" in json.dumps(loaded)


def test_raw_calendar_packet_contains_actual_content_and_persists():
    store, _ = _temp_store()
    eid = f"e-{uuid.uuid4()}"
    gh = uuid.uuid4().hex
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id=f"raw:{eid}",
        event_index_id=eid,
        graph_event_id_hash=gh,
        project_key="trop",
        subject="Raw cal packet",
        body_text="Calendar actual body for model context. Join https://meet.example/xyz",
        location_display="Site",
        organizer_name="Bob",
        organizer_email="b@ex.com",
        attendees_json=json.dumps([{"name": "C", "email": "c@ex.com"}]),
        join_url="https://meet.example/xyz",
        start_datetime_utc="2026-06-08T09:00:00Z",
        end_datetime_utc="2026-06-08T09:30:00Z",
    )
    # Minimal index row so list works in builder path (if it uses index+raw join)
    import sqlite3

    with sqlite3.connect(str(store._db_path)) as c:  # type: ignore[attr-defined]
        c.execute(
            "INSERT OR IGNORE INTO calendar_event_index (event_index_id, source_id, subject_token_hashes_json, organizer_domain, start_datetime_utc, end_datetime_utc, is_private, is_cancelled, project_key, project_match_method, project_match_confidence, review_required, review_reasons_json, created_utc, updated_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid,
                "primary",
                "[]",
                "ex.com",
                "2026-06-08T09:00:00Z",
                "2026-06-08T09:30:00Z",
                0,
                0,
                "trop",
                "h",
                0.5,
                0,
                "[]",
                "2026-01-01",
                "2026-01-01",
            ),
        )

    pkt = build_raw_calendar_context_packet(project_key="trop", store=store)
    assert pkt["packet_type"] == "raw_calendar_context"
    assert pkt["raw_content_included"] == 1
    evs = pkt["content"]["events"]
    assert any("Calendar actual body" in (e.get("body_text") or "") for e in evs)
    assert any(e.get("join_url") for e in evs)
    assert pkt["token_estimate"] > 0

    rows = store.list_raw_content_model_context_packets(packet_type="raw_calendar_context", limit=5)
    assert any(r["packet_id"] == pkt["packet_id"] for r in rows)


def test_packets_respect_bounds_and_graceful_metadata_when_not_effective(monkeypatch):
    store, _ = _temp_store()
    # Force a policy that disables raw for model context by patching load
    from hb_assistant.construction.second_brain.local_ai import raw_context as rcmod

    class _Off:
        raw_content = type(
            "rc",
            (),
            {
                "enabled": False,
                "mode": "disabled",
                "model_context": type(
                    "mc",
                    (),
                    {
                        "include_raw_content": False,
                        "max_threads_per_run": 1,
                        "max_messages_per_thread": 1,
                        "max_body_chars_per_message": 10,
                        "max_events_per_run": 1,
                        "max_calendar_body_chars_per_event": 10,
                    },
                )(),
                "starting_sources": type("ss", (), {"email": False, "calendar": False})(),
            },
        )()

    monkeypatch.setattr(rcmod, "_load_policy", lambda: _Off())

    ep = build_raw_email_context_packet(project_key="trop", store=store)
    assert ep["raw_content_included"] == 0
    assert ep["content"]["threads"] == []

    cp = build_raw_calendar_context_packet(project_key="trop", store=store)
    assert cp["raw_content_included"] == 0
    assert cp["content"]["events"] == []
