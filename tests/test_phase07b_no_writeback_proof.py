"""Phase 07B Prompt 12 — no-writeback / no-secret / no-raw-body proof (07B coverage).

Proves the extended prover covers the Phase 07B surfaces: the 10 07B modules (mutation
verbs / banned HTTP imports / secrets), the V11/V14/V23 guard CHECK columns, the persisted
content of the 07B tables, and the 07B evidence dir — all folded into proof_passed and
fail-closed. Findings are pattern labels + table.column locations only (never the value).
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

from hb_assistant.construction.data_quality.safety import (
    build_data_quality_no_writeback_proof,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_07B_KEYS = (
    "static_writeback_scan_07b_modules",
    "no_http_client_or_mutation_imports_07b",
    "module_secret_scan_07b",
    "sqlite_guardrail_07b_tables",
    "sqlite_content_leak_scan_07b_tables",
    "evidence_output_scan_07b",
)
_07A_KEYS = (
    "static_writeback_scan_07a_modules",
    "sqlite_raw_body_guardrail_v20_v21_07a_tables",
    "evidence_output_scan_07a",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_07b_nwb_")
    os.close(fd)
    with contextlib.suppress(Exception):
        SQLiteMigrator(db_path=db).apply()
    return db


def test_clean_pass_and_covers_07a_and_07b() -> None:
    db = _fresh_db()
    try:
        report = build_data_quality_no_writeback_proof(db_path=db)
        assert report["proof_passed"] is True
        checks = report["checks_detail"]
        for key in _07A_KEYS + _07B_KEYS:
            assert key in checks, key
            assert checks[key]["passed"] is True, (key, checks[key]["findings"])
        # All 10 07B modules were on disk and scanned; event_indexer is among them.
        assert len(report["scanned_modules_07b"]) == 10
        assert any("event_indexer.py" in m for m in report["scanned_modules_07b"])
        # The guard probe lists the guarded 07B tables with their CHECK columns.
        guarded = {t["table"] for t in checks["sqlite_guardrail_07b_tables"]["tables"]}
        assert {"calendar_event_index", "email_model_classifications",
                "meeting_email_relationship_candidates"} <= guarded
    finally:
        os.unlink(db)


def test_populated_store_still_passes_content_scan() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db)
        now = _now()
        store.upsert_calendar_source_location(source_id="primary_calendar", mailbox_owner_hash="o")
        store.upsert_calendar_event_index(
            event_index_id="E1", source_id="primary_calendar", graph_event_id_hash="g1",
            start_datetime_utc=now, end_datetime_utc=now, organizer_domain="vendor.com",
        )
        store.upsert_email_source_location(
            source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
        )
        store.upsert_email_message(message_id="m1", thread_key="T1", source_id="sx",
                                   received_datetime=now)
        store.upsert_email_model_classification(
            classification_id="c1", message_id="m1", model_name="mistral",
            schema_version="phase06-email-ollama-v1", classification_status="valid",
        )
        store.upsert_email_thread_summary(
            thread_key="T1", project_key="tropical", message_count=1,
            first_message_datetime=now, last_message_datetime=now,
            summary_redacted="thread: 1 message(s), 1 participant(s)",
            summary_policy="metadata_only",
        )
        store.upsert_meeting_email_relationship_candidate(
            candidate_id="cand1", event_index_id="E1", thread_key_hash="abc123",
            candidate_type="time_and_domain",
            source_reference_json=json.dumps({"event_index_id": "E1", "event_start_utc": now}),
            confidence=0.8, confidence_class="strong", review_required=False,
        )

        report = build_data_quality_no_writeback_proof(db_path=db)
        assert report["proof_passed"] is True
        content = report["checks_detail"]["sqlite_content_leak_scan_07b_tables"]
        assert content["passed"] is True
        assert content["findings"] == []
        assert "email_thread_summaries" in content["scanned_tables"]
    finally:
        os.unlink(db)


def test_fail_closed_on_raw_email_in_content() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db)
        # A metadata-only 07B table with no blocking CHECK — inject a raw email.
        store.upsert_email_thread_summary(
            thread_key="T1", project_key="tropical", message_count=1,
            summary_redacted="ping me at vendor.person@example.com about the RFI",
            summary_policy="metadata_only",
        )
        report = build_data_quality_no_writeback_proof(db_path=db)
        assert report["proof_passed"] is False
        content = report["checks_detail"]["sqlite_content_leak_scan_07b_tables"]
        assert content["passed"] is False
        assert any(
            f.startswith("email_thread_summaries.summary_redacted:") and "raw_email_address" in f
            for f in content["findings"]
        )
        # The proof must never echo the offending value.
        assert "vendor.person@example.com" not in json.dumps(report)
    finally:
        os.unlink(db)


def test_fail_closed_on_signed_url_in_content() -> None:
    db = _fresh_db()
    try:
        # Direct insert of a signed/download URL into a 07B text column.
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "INSERT INTO email_thread_summaries (thread_key, summary_redacted, summary_policy) "
                "VALUES (?, ?, ?)",
                ("T2", "see https://files.example.com/d?sig=ABCDEFGHIJKLMNOP", "metadata_only"),
            )
            conn.commit()
        finally:
            conn.close()
        report = build_data_quality_no_writeback_proof(db_path=db)
        assert report["proof_passed"] is False
        findings = report["checks_detail"]["sqlite_content_leak_scan_07b_tables"]["findings"]
        assert any("http_url" in f for f in findings)
        assert "files.example.com" not in json.dumps(report)
    finally:
        os.unlink(db)
