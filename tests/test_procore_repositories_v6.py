"""Phase 04A V6 schema + procore_repositories functional tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_repositories import (
    count_procore_live_records,
    get_sync_run,
    record_sync_run_complete,
    record_sync_run_start,
    update_watermark,
    upsert_procore_live_record,
)

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _migrate(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()


def test_v6_migration_creates_three_procore_live_tables() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'procore_live_%'"
            )
        }
    finally:
        conn.close()
    assert tables == {
        "procore_live_sync_runs",
        "procore_live_records",
        "procore_live_sync_watermarks",
    }


def test_v6_migration_is_idempotent() -> None:
    db = _temp_db()
    _migrate(db)
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 6"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == 1


def test_upsert_inserts_then_updates() -> None:
    db = _temp_db()
    _migrate(db)
    record_sync_run_start(
        sync_run_id="run-1",
        endpoint_id="rfis",
        command_endpoint="rfis",
        legacy_endpoint_alias="list-rfis",
        project_key="tropical",
        procore_project_id="2525840",
        company_id="5280",
        mode="live_apply",
        started_at_utc="2026-01-01T00:00:00+00:00",
        db_path=db,
    )

    first = upsert_procore_live_record(
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="rfis",
        procore_record_id="42",
        parent_procore_id=None,
        normalized_fields={"number": "RFI-001", "status": "open", "updated_at": "2026-01-01"},
        review_required=False,
        sensitive_reason=None,
        source_url_redacted="/rest/v1.0/projects/2525840/rfis",
        last_sync_run_id="run-1",
        now_utc="2026-01-01T00:00:00+00:00",
        db_path=db,
    )
    assert first == "inserted"

    second = upsert_procore_live_record(
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="rfis",
        procore_record_id="42",
        parent_procore_id=None,
        normalized_fields={"number": "RFI-001", "status": "closed", "updated_at": "2026-01-02"},
        review_required=True,
        sensitive_reason="status_change",
        source_url_redacted="/rest/v1.0/projects/2525840/rfis",
        last_sync_run_id="run-1",
        now_utc="2026-01-02T00:00:00+00:00",
        db_path=db,
    )
    assert second == "updated"

    assert count_procore_live_records(
        project_key="tropical", endpoint_id="rfis", db_path=db
    ) == 1

    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT status, review_required FROM procore_live_records WHERE procore_record_id = '42'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "closed"
    assert row[1] == 1


def test_record_sync_run_lifecycle() -> None:
    db = _temp_db()
    _migrate(db)
    record_sync_run_start(
        sync_run_id="run-2",
        endpoint_id="rfis",
        command_endpoint="rfis",
        legacy_endpoint_alias="list-rfis",
        project_key="tropical",
        procore_project_id="2525840",
        company_id="5280",
        mode="live_apply",
        started_at_utc="2026-01-01T00:00:00+00:00",
        db_path=db,
    )
    record_sync_run_complete(
        sync_run_id="run-2",
        status="success",
        state="success",
        reason_codes=[],
        request_count=1,
        retrieved_count=3,
        normalized_count=3,
        sqlite_upserted_count=3,
        evidence_path="docs/evidence/x.md",
        completed_at_utc="2026-01-01T00:01:00+00:00",
        no_live_call_performed=False,
        db_path=db,
    )

    run = get_sync_run(sync_run_id="run-2", db_path=db)
    assert run is not None
    assert run["status"] == "success"
    assert run["retrieved_count"] == 3
    assert run["sqlite_upserted_count"] == 3
    assert run["raw_body_persisted"] == 0
    assert run["redaction_applied"] == 1


def test_watermark_is_upsert_keyed_on_company_project_endpoint() -> None:
    db = _temp_db()
    _migrate(db)
    update_watermark(
        company_id="5280",
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="rfis",
        cursor_redacted=None,
        receipt_id="r-1",
        now_utc="2026-01-01T00:00:00+00:00",
        db_path=db,
    )
    update_watermark(
        company_id="5280",
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="rfis",
        cursor_redacted=None,
        receipt_id="r-2",
        now_utc="2026-01-02T00:00:00+00:00",
        db_path=db,
    )
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT last_receipt_id FROM procore_live_sync_watermarks WHERE project_key = 'tropical'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "r-2"


def test_raw_body_persisted_check_constraint_rejects_one() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO procore_live_sync_runs (
                  sync_run_id, endpoint_id, command_endpoint, project_key,
                  procore_project_id, company_id, mode, started_at_utc,
                  status, state, redaction_applied, raw_body_persisted
                ) VALUES (
                  'bad', 'rfis', 'rfis', 'tropical', '2525840', '5280',
                  'live_apply', '2026-01-01T00:00:00+00:00',
                  'success', 'success', 1, 1
                )
                """
            )
    finally:
        conn.close()
