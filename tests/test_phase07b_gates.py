"""Phase 07B Prompt 11 — 07B data-quality gates (calendar/email/thread/candidate readiness).

Proves: the four manifest-driven 07B presence gates exist and are deferred on an empty store;
they PASS once their V23/V14/V11 tables hold rows (incl. a regression that
`calendar_population_status` reads `calendar_event_index`, not the old non-existent
`calendar_events`); and Phase 07D meeting-prep readiness stays blocked (ready=False) until
every prerequisite — including the still-absent 07C document gate — passes.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.construction.data_quality import evaluate_data_quality_gates
from hb_assistant.construction.data_quality.gates import _load_phase_07b_gate_manifest
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_07B_GATES = (
    "calendar_population_status",
    "email_classifier_persistence_status",
    "email_thread_summary_population_status",
    "meeting_email_candidate_population_status",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_07b_gates_")
    import os

    os.close(fd)
    with contextlib.suppress(Exception):
        SQLiteMigrator(db_path=db).apply()
    return db


def _status_map(report: dict) -> dict:
    return {g["gate_name"]: g["gate_status"] for g in report["gates"]}


def _phase_map(report: dict) -> dict:
    return {g["gate_name"]: g.get("future_phase") for g in report["gates"]}


def _meeting_prep(report: dict) -> dict:
    return report["phase_go_nogo"]["07D"]["meeting_prep_readiness"]


def test_empty_store_defers_07b_gates_and_blocks_meeting_prep() -> None:
    db = _fresh_db()
    try:
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        statuses = _status_map(report)
        for gate in _07B_GATES:
            assert statuses[gate] == "deferred_not_blocking", (gate, statuses.get(gate))
        assert report["meeting_prep_readiness_claim"] in ("blocked", "needs_07b_07c_data")
        prep = _meeting_prep(report)
        assert prep["ready"] is False
        assert prep["auto_readiness_allowed"] is False
        assert set(_07B_GATES) <= set(prep["blocked_by"])
    finally:
        Path(db).unlink(missing_ok=True)


def test_populated_store_passes_07b_gates_but_07c_keeps_meeting_prep_blocked() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db)
        now = _now()
        # Calendar (V23) — regression target: gate must read calendar_event_index.
        store.upsert_calendar_source_location(source_id="primary_calendar", mailbox_owner_hash="o")
        store.upsert_calendar_event_index(
            event_index_id="E1", source_id="primary_calendar", graph_event_id_hash="g1",
            start_datetime_utc=now, end_datetime_utc=now,
        )
        # Email message + classification (V14).
        store.upsert_email_source_location(
            source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
        )
        store.upsert_email_message(message_id="m1", thread_key="T1", source_id="sx",
                                   received_datetime=now)
        store.upsert_email_model_classification(
            classification_id="c1", message_id="m1", model_name="mistral",
            schema_version="phase06-email-ollama-v1", classification_status="valid",
        )
        # Thread summary (V11).
        store.upsert_email_thread_summary(
            thread_key="T1", project_key="tropical", message_count=1,
            first_message_datetime=now, last_message_datetime=now,
            summary_redacted="thread: 1 message(s)", summary_policy="metadata_only",
        )
        # Meeting<->email candidate (V23).
        store.upsert_meeting_email_relationship_candidate(
            candidate_id="cand1", event_index_id="E1", thread_key_hash="abc123",
            candidate_type="time_and_domain", source_reference_json=json.dumps({"event_index_id": "E1"}),
            confidence=0.8, confidence_class="strong", review_required=False,
        )

        report = evaluate_data_quality_gates(db_path=db, persist=False)
        statuses = _status_map(report)
        for gate in _07B_GATES:
            assert statuses[gate] == "pass", (gate, statuses.get(gate))
        # Regression: the calendar gate now reads calendar_event_index (would defer under the bug).
        assert statuses["calendar_population_status"] == "pass"

        prep = _meeting_prep(report)
        assert prep["ready"] is False  # 07C still missing
        # No 07B gate blocks meeting prep; the 07C document gate does.
        for gate in _07B_GATES:
            assert gate not in prep["blocked_by"]
        assert "document_card_population_status" in prep["blocked_by"]
        assert report["meeting_prep_readiness_claim"] != "ready"
    finally:
        Path(db).unlink(missing_ok=True)


def test_manifest_matches_implemented_gates() -> None:
    db = _fresh_db()
    try:
        report = evaluate_data_quality_gates(db_path=db, persist=False)
        phases = _phase_map(report)
        manifest = _load_phase_07b_gate_manifest()
        for gate in manifest["gates"]:
            assert phases.get(gate["name"]) == "07B", gate["name"]
        assert manifest["auto_readiness_allowed"] is False
        assert len(report["gates"]) >= 12
        assert report["meeting_prep_readiness_claim"] != "ready"
    finally:
        Path(db).unlink(missing_ok=True)
