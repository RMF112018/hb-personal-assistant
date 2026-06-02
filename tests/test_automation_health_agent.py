"""Phase 08B Prompt 03 — Automation Health Agent (deterministic, offline, read-only)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.automation_health import (
    build_automation_health_proof,
    evaluate_automation_health,
    run_automation_health,
)
from hb_assistant.construction.store import ConstructionStore

_FORBIDDEN = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "health.sqlite")


def test_migrated_db_is_healthy(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate to LATEST
    status = evaluate_automation_health(db_path=db_path)
    assert status.overall_status == "ok"
    assert status.reason_code == "RUN_OK"
    assert {c.check for c in status.checks} >= {
        "path_readiness",
        "store_readiness",
        "schema_at_latest",
        "daily_brief_handoff_durable",
    }
    assert all(c.status == "ok" for c in status.checks)
    assert status.degraded_checks == []


def test_unmigrated_db_is_degraded_with_reason_codes(db_path: str) -> None:
    # An empty (unmigrated) DB: store/schema/handoff checks degrade with HEALTH_CHECK_FAILED.
    sqlite3.connect(db_path).close()
    status = evaluate_automation_health(db_path=db_path)
    assert status.overall_status == "degraded"
    assert status.reason_code == "RUN_DEGRADED"
    degraded = {c.check: c for c in status.checks if c.status != "ok"}
    assert "schema_at_latest" in degraded
    assert "daily_brief_handoff_durable" in degraded
    for c in degraded.values():
        assert c.reason_code == "HEALTH_CHECK_FAILED"


def test_stale_schema_check_reports_detail(db_path: str) -> None:
    # A DB with a stale (absent) durable-handoff table reports an actionable, no-raw detail.
    sqlite3.connect(db_path).close()
    status = evaluate_automation_health(db_path=db_path)
    handoff = next(c for c in status.checks if c.check == "daily_brief_handoff_durable")
    assert handoff.status == "degraded"
    assert handoff.detail == "table_absent"


def test_emit_persists_metadata_only_receipt(db_path: str) -> None:
    ConstructionStore(db_path)
    status, agent_run_id = run_automation_health(db_path=db_path, emit_receipt=True)
    assert agent_run_id is not None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM second_brain_agent_run_receipts").fetchone())
    assert row["agent_id"] == "automation_health_agent"
    assert row["run_kind"] == "health_check"
    assert row["status"] == status.overall_status
    assert row["reason_code"] == status.reason_code
    for col, value in row.items():
        if col.endswith("_persisted") or col == "external_writeback_performed":
            assert value == 0, f"guard {col} must be 0"
    values_blob = " ".join(str(v) for v in row.values())
    for forbidden in _FORBIDDEN:
        assert forbidden not in values_blob


def test_dry_run_default_writes_no_receipt(db_path: str) -> None:
    ConstructionStore(db_path)
    status, agent_run_id = run_automation_health(db_path=db_path, emit_receipt=False)
    assert agent_run_id is None
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM second_brain_agent_run_receipts").fetchone()[0] == 0


def test_evaluation_carries_no_raw_content(db_path: str) -> None:
    ConstructionStore(db_path)
    blob = evaluate_automation_health(db_path=db_path).model_dump_json()
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob


def test_proof_passes() -> None:
    proof = build_automation_health_proof()
    assert proof["proof_passed"] is True
    assert proof["overall_status"] == "ok"
    assert proof["reason_code"] == "RUN_OK"
    assert proof["no_raw_content"] is True
