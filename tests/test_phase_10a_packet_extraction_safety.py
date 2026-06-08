"""Phase 10A — packet extraction safety: dry-run zero writes, triage no-persist, linkage."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import (
    build_email_thread_action_packet,
    build_triage_batch_packet,
    extract_actions_for_packet,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.store import ConstructionStore

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
