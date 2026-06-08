"""Phase 10 / 10A — raw action extraction hardening.

Covers the correctness fixes to the raw email/calendar → action-candidate path:
- HTML-to-text normalization: packet builders produce clean text from body_html when body_text is empty;
- dry-run performs ZERO writes across task_candidates / commitment_candidates / candidate_source_refs /
  local_model_run_receipts; --apply persists after validation;
- candidate_source_refs.candidate_id matches the persisted candidate candidate_id;
- deterministic SHA-256 stable keys → idempotent dedupe (apply twice ⇒ one row);
- --source filtering is honored.
Fully offline — no Ollama, no network.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import uuid
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import (
    build_raw_calendar_context_packet,
    build_raw_email_context_packet,
    extract_action_candidates_from_raw,
)
from hb_assistant.construction.second_brain.local_ai.raw_context import _normalized_body_text
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.store import ConstructionStore

_EMAIL_PACKET = {
    "content": {
        "threads": [
            {
                "thread_subject": "RFI follow-up",
                "messages": [
                    {
                        "id": "msg-1",
                        "subject": "RFI follow-up",
                        "body_text": "Please submit the revised RFI sketch by Friday.",
                    }
                ],
            }
        ]
    }
}


def _task_mock() -> str:
    return json.dumps(
        [
            {
                "candidate_type": "task",
                "title": "Submit revised RFI sketch by Friday",
                "project_key": "P1",
                "assignee": "user",
                "due_at": None,
                "urgency": "normal",
                "waiting_state": "waiting_on_me",
                "source_refs": ["msg-1"],
                "confidence": 0.8,
                "reason": "Sender asks to submit the revised sketch by Friday.",
                "safety_category": "normal",
                "recommended_next_action": "review",
                "review_status": "pending",
                "external_action_requires_approval": True,
            }
        ]
    )


def _store(td: str) -> tuple[ConstructionStore, str]:
    db = str(Path(td) / "p10a_hardening.db")
    return ConstructionStore(db_path=db), db


def _guard_sum(db: str, table: str) -> int:
    conn = sqlite3.connect(db)
    expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
    val = conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]
    conn.close()
    return int(val or 0)


# --------------------------------------------------------------------------------------------------
# HTML-to-text normalization.
# --------------------------------------------------------------------------------------------------
def test_normalized_body_text_helper() -> None:
    # body_text empty → derive clean text from body_html (tags stripped, entities unescaped).
    assert _normalized_body_text("", "<p>Hello&nbsp;<b>world</b></p>", 2000) == "Hello world"
    assert _normalized_body_text(None, "<div>Submit by &amp; Friday</div>", 2000) == "Submit by & Friday"
    # body_text present → returned as-is (no HTML processing).
    assert _normalized_body_text("plain text", "<p>ignored</p>", 2000) == "plain text"
    # neither → falsy passthrough.
    assert not _normalized_body_text("", None, 2000)


def test_email_packet_normalizes_html_when_text_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        store.upsert_email_message_raw_content(
            raw_email_id=f"raw:{uuid.uuid4()}",
            message_id_hash="mh-1",
            conversation_id_hash="ch-1",
            project_key="trop",
            subject="HTML only",
            body_text="",  # empty → must fall back to normalized HTML
            body_html="<p>Hello <b>world</b> &amp; please review</p>",
            from_name="Alice",
            from_address="a@ex.com",
            to_recipients_json="[]",
            sent_at_utc="2026-06-07T12:00:00Z",
        )
        pkt = build_raw_email_context_packet(project_key="trop", store=store)
        texts = [
            m.get("body_text")
            for t in pkt["content"]["threads"]
            for m in t.get("messages", [])
        ]
        assert any(bt and "Hello world & please review" in bt for bt in texts), texts
        assert all("<" not in (bt or "") for bt in texts)  # no raw tags in the text field


def test_calendar_packet_normalizes_html_when_text_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        eid = f"e-{uuid.uuid4()}"
        store.upsert_calendar_event_raw_content(
            raw_calendar_event_id=f"raw:{eid}",
            event_index_id=eid,
            graph_event_id_hash=uuid.uuid4().hex,
            project_key="trop",
            subject="HTML cal",
            body_text="",
            body_html="<p>Pre-bid <i>walk</i> at site</p>",
            location_display="Site",
            organizer_name="Bob",
            organizer_email="b@ex.com",
            attendees_json="[]",
            start_datetime_utc="2026-06-08T09:00:00Z",
            end_datetime_utc="2026-06-08T09:30:00Z",
        )
        with sqlite3.connect(str(store._db_path)) as c:  # type: ignore[attr-defined]
            c.execute(
                "INSERT OR IGNORE INTO calendar_event_index (event_index_id, source_id, "
                "subject_token_hashes_json, organizer_domain, start_datetime_utc, end_datetime_utc, "
                "is_private, is_cancelled, project_key, project_match_method, project_match_confidence, "
                "review_required, review_reasons_json, created_utc, updated_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, "primary", "[]", "ex.com", "2026-06-08T09:00:00Z", "2026-06-08T09:30:00Z",
                 0, 0, "trop", "h", 0.5, 0, "[]", "2026-01-01", "2026-01-01"),
            )
        pkt = build_raw_calendar_context_packet(project_key="trop", store=store)
        texts = [e.get("body_text") for e in pkt["content"]["events"]]
        assert any(bt and "Pre-bid walk at site" in bt for bt in texts), texts
        assert all("<" not in (bt or "") for bt in texts)


# --------------------------------------------------------------------------------------------------
# Dry-run zero writes / apply / linkage / dedupe / source filtering.
# --------------------------------------------------------------------------------------------------
def test_dry_run_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        rep = extract_action_candidates_from_raw(
            raw_email_packet=_EMAIL_PACKET, store=store, mock_output=_task_mock(),
            dry_run=True, project_key="P1",
        )
        assert rep["accepted"] == 1 and rep["persisted"] == 0 and rep["would_persist"] == 1
        assert rep["dry_run"] is True
        assert store.list_task_candidates() == []
        assert store.list_commitment_candidates() == []
        assert store.list_candidate_source_refs(candidate_type="task") == []
        assert store.list_local_model_run_receipts() == []


def test_apply_persists_and_links_source_ref() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, db = _store(td)
        rep = extract_action_candidates_from_raw(
            raw_email_packet=_EMAIL_PACKET, store=store, mock_output=_task_mock(),
            dry_run=False, project_key="P1",
        )
        assert rep["persisted"] == 1
        tasks = store.list_task_candidates()
        refs = store.list_candidate_source_refs(candidate_type="task")
        assert len(tasks) == 1 and len(refs) == 1
        assert refs[0]["candidate_id"] == tasks[0]["candidate_id"]
        assert tasks[0]["stable_key"].startswith("raw-task:")
        for table in ("task_candidates", "candidate_source_refs"):
            assert _guard_sum(db, table) == 0


def test_deterministic_dedupe_on_reapply() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        for _ in range(2):
            extract_action_candidates_from_raw(
                raw_email_packet=_EMAIL_PACKET, store=store, mock_output=_task_mock(),
                dry_run=False, project_key="P1",
            )
        assert len(store.list_task_candidates()) == 1
        assert len(store.list_candidate_source_refs(candidate_type="task")) == 1


def test_source_filter_calendar_only_ignores_email_packet() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        rep = extract_action_candidates_from_raw(
            raw_email_packet=_EMAIL_PACKET, store=store, mock_output=_task_mock(),
            dry_run=True, source="calendar",
        )
        assert rep["produced"] == 0
        assert "no raw content" in (rep.get("note") or "")
