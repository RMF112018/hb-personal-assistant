"""Phase 10A — packet extraction safety: dry-run zero writes, triage no-persist, linkage."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import (
    build_email_thread_action_packet,
    build_related_context_action_packet,
    build_triage_batch_packet,
    extract_actions_for_packet,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_RAW_TABLES = ("task_candidates", "commitment_candidates", "candidate_source_refs",
               "local_model_run_receipts")


def _seed_thread(store: ConstructionStore, *, thread_ref: str = "t1", msg_id: str = "m1") -> None:
    store.upsert_email_thread_raw_context(
        raw_thread_context_id=f"rtc-{thread_ref}", thread_ref=thread_ref, project_key="P",
        message_count=1, thread_subject="RFI 42 follow-up",
        messages_json=json.dumps([{"id": msg_id, "subject": "RFI 42 follow-up",
                                   "body_text": "Please submit the revised RFI 42 sketch by Friday.",
                                   "sent_at_utc": "2026-06-07T12:00:00+00:00"}]),
        source_refs_json="[]", model_ready=1,
    )


def _candidate(source_ref: str = "m1") -> str:
    return json.dumps([{
        "candidate_type": "task", "title": "Submit revised RFI 42 sketch by Friday",
        "project_key": "P", "assignee": "user", "due_at": None, "urgency": "normal",
        "waiting_state": "waiting_on_me", "source_refs": [source_ref], "confidence": 0.85,
        "reason": "Email asks to submit the revised RFI 42 sketch by Friday.",
        "safety_category": "normal", "recommended_next_action": "review",
        "review_status": "pending", "external_action_requires_approval": True,
    }])


def _counts(store: ConstructionStore) -> dict:
    return {
        "task": len(store.list_task_candidates()),
        "commitment": len(store.list_commitment_candidates()),
        "refs": len(store.list_candidate_source_refs(candidate_type="task")),
        "receipts": len(store.list_local_model_run_receipts()),
    }


def test_dry_run_extraction_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "x.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output=_candidate())
        assert rep["extracted"] is True and rep["accepted"] == 1 and rep["persisted"] == 0
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0, "receipts": 0}


def test_triage_packet_cannot_persist_candidates() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "x2.db"))
        _seed_thread(s)
        triage = build_triage_batch_packet(store=s)
        # Even on apply, a triage packet never persists task/commitment candidates.
        rep = extract_actions_for_packet(packet=triage, store=s, dry_run=False, mock_output=_candidate())
        assert rep["extracted"] is False
        assert rep["persisted"] == 0
        assert rep["note"] == "purpose_does_not_allow_candidate_actions"
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0, "receipts": 0}


def test_apply_persists_after_validation_with_linkage() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "x3.db")
        s = ConstructionStore(db_path=db)
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=_candidate())
        assert rep["persisted"] == 1
        tasks = s.list_task_candidates()
        refs = s.list_candidate_source_refs(candidate_type="task")
        assert len(tasks) == 1 and len(refs) == 1
        assert refs[0]["candidate_id"] == tasks[0]["candidate_id"]  # linkage to persisted id
        assert refs[0]["source_ref_hash"] == "m1"  # resolves back to the raw message
        conn = sqlite3.connect(db)
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        for table in ("task_candidates", "candidate_source_refs"):
            assert int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]) == 0
        conn.close()


def test_apply_rejects_generic_candidate() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "x4.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        generic = json.dumps([{
            "candidate_type": "task", "title": "Analyze the data and clean up the fields",
            "project_key": "P", "assignee": "user", "due_at": None, "urgency": "low",
            "waiting_state": "unknown", "source_refs": ["m1"], "confidence": 0.6,
            "reason": "Perform data analysis and normalize the spreadsheet fields.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }])
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=False, mock_output=generic)
        assert rep["accepted"] == 0 and rep["persisted"] == 0
        assert s.list_task_candidates() == []


def _seed_strong_pair(store: ConstructionStore) -> None:
    """A strongly-related thread + event (same project, RFI 42, participant + time overlap)."""
    store.upsert_email_thread_raw_context(
        raw_thread_context_id="rtc-t1", thread_ref="t1", project_key="HILL", message_count=1,
        thread_subject="Hilltop RFI 42 coordination",
        messages_json=json.dumps([{"id": "m1", "subject": "Hilltop RFI 42 coordination",
                                   "from_address": "pm@sub.com", "to_recipients": ["bob@hbcd.com"],
                                   "body_text": "Confirm the revised RFI 42 sketch before the meeting.",
                                   "sent_at_utc": "2026-06-07T12:00:00+00:00"}]),
        source_refs_json="[]", model_ready=1,
    )
    store.upsert_calendar_event_raw_content(
        raw_calendar_event_id="raw:e1", event_index_id="e1", graph_event_id_hash="gh1",
        project_key="HILL", subject="Hilltop RFI 42 coordination", body_text="Discuss RFI 42",
        organizer_name="PM", organizer_email="pm@sub.com",
        attendees_json=json.dumps([{"email": "bob@hbcd.com"}]),
        start_datetime_utc="2026-06-08T09:00:00+00:00", end_datetime_utc="2026-06-08T09:30:00+00:00",
    )


def test_blocked_related_packet_never_calls_model() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "blk.db"))
        # Unrelated thread + event → related packet does not compile.
        s.upsert_email_thread_raw_context(
            raw_thread_context_id="rtc-t1", thread_ref="t1", project_key="A", message_count=1,
            thread_subject="Lunch order",
            messages_json=json.dumps([{"id": "m1", "body_text": "sandwiches"}]),
            source_refs_json="[]", model_ready=1,
        )
        s.upsert_calendar_event_raw_content(
            raw_calendar_event_id="raw:e1", event_index_id="e1", graph_event_id_hash="gh1",
            project_key="B", subject="Budget review", body_text="numbers",
            organizer_email="z@c.com", attendees_json="[]",
            start_datetime_utc="2026-06-08T09:00:00+00:00", end_datetime_utc="2026-06-08T09:30:00+00:00",
        )
        packet = build_related_context_action_packet(thread_ref="t1", store=s)
        assert packet["compiled"] is False
        # A mock that WOULD produce a candidate; the blocked packet must ignore it (no model call).
        rep = extract_actions_for_packet(packet=packet, store=s, dry_run=False, mock_output=_candidate())
        assert rep["extracted"] is False and rep["blocked"] is True and rep["persisted"] == 0
        assert rep["candidates"] == []
        assert rep["note"] == "no_strong_or_moderate_relationship"
        assert "best_confidence" in rep
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0, "receipts": 0}


def test_related_packet_per_ref_source_family_attribution() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "fam.db"))
        _seed_strong_pair(s)
        packet = build_related_context_action_packet(thread_ref="t1", store=s)
        assert packet["compiled"] is True and packet["content"]["events"]
        # Candidate cites BOTH the email message ref and the calendar event ref.
        cand = json.dumps([{
            "candidate_type": "task", "title": "Confirm revised RFI 42 sketch before the meeting",
            "project_key": "HILL", "assignee": "user", "due_at": None, "urgency": "normal",
            "waiting_state": "waiting_on_me", "source_refs": ["m1", "e1"], "confidence": 0.85,
            "reason": "Email asks to confirm RFI 42 sketch before the coordination meeting.",
            "safety_category": "normal", "recommended_next_action": "review",
            "review_status": "pending", "external_action_requires_approval": True,
        }])
        rep = extract_actions_for_packet(packet=packet, store=s, dry_run=False, mock_output=cand)
        assert rep["persisted"] == 1
        refs = s.list_candidate_source_refs(candidate_type="task")
        fam = {r["source_ref_hash"]: r["source_family"] for r in refs}
        assert fam["m1"] == "email_message_raw_content"
        assert fam["e1"] == "calendar_event_raw_content"  # not inferred as email


def test_no_output_run_returns_safe_diagnostics() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "diag.db"))
        _seed_thread(s)
        pkt = build_email_thread_action_packet(thread_ref="t1", store=s)
        # No mock + no client → no model output → diagnostics, no writes.
        rep = extract_actions_for_packet(packet=pkt, store=s, dry_run=True, mock_output=None)
        diag = rep["diagnostics"]
        assert diag["prompt_char_count"] > 0
        assert diag["packet_char_estimate"] >= 0
        assert diag["endpoint_reachable"] is None  # no live client attempted
        assert diag["model_name"] is None
        assert diag["error_class_redacted"] is None
        # diagnostics carry no raw body / URL / token.
        assert "http" not in json.dumps(diag).lower()


def test_cli_extract_packet_dry_run_is_default_and_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "cli.db")
        ConstructionStore(db_path=db)  # migrate
        s = ConstructionStore(db_path=db)
        _seed_thread(s)
        # Default (no flag) is dry-run; --mock-output is the offline path.
        res = runner.invoke(
            app,
            ["phase-10", "extract-packet", "--thread-ref", "t1", "--mock-output", _candidate(),
             "--db", db, "--json"],
        )
        assert res.exit_code == 0, res.output
        body = json.loads(res.output)
        assert body["applied"] is False and body["guardrails"]["dry_run"] is True
        assert s.list_task_candidates() == []
        # Explicit --dry-run behaves the same.
        res2 = runner.invoke(
            app,
            ["phase-10", "extract-packet", "--thread-ref", "t1", "--mock-output", _candidate(),
             "--dry-run", "--db", db, "--json"],
        )
        assert res2.exit_code == 0
        assert json.loads(res2.output)["applied"] is False
        assert s.list_task_candidates() == []
