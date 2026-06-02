"""Phase 08B Prompt 08 — daily-brief job health monitoring."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.daily_brief_health import (
    build_daily_brief_job_health_proof,
    evaluate_daily_brief_job_health,
    run_daily_brief_job_health,
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

_NOW = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    db = str(tmp_path / "brief.sqlite")
    ConstructionStore(db)
    return db


def _insert_run(
    db_path: str, *, status: str, generated_utc: str, degradation: str | None = None
) -> None:
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO daily_brief_runs
                (brief_run_id, brief_date, mode, status, degradation_mode, generated_utc)
            VALUES (?, '2026-06-02', 'apply', ?, ?, ?)
            """,
            (uuid.uuid4().hex, status, degradation, generated_utc),
        )
    conn.close()


def test_never_run(db_path: str) -> None:
    status = evaluate_daily_brief_job_health(db_path=db_path, now=_NOW)
    assert status.reason_code == "JOB_NEVER_RUN"
    assert status.overall_status == "attention"


def test_healthy(db_path: str) -> None:
    _insert_run(
        db_path, status="synthesized", generated_utc=(_NOW - timedelta(hours=1)).isoformat()
    )
    status = evaluate_daily_brief_job_health(db_path=db_path, now=_NOW)
    assert status.reason_code == "JOB_HEALTHY"
    assert status.overall_status == "ok"
    assert status.last_run_status == "synthesized"


def test_degraded_blocked(db_path: str) -> None:
    _insert_run(
        db_path,
        status="blocked",
        generated_utc=(_NOW - timedelta(hours=1)).isoformat(),
        degradation="research_packet_blocked",
    )
    status = evaluate_daily_brief_job_health(db_path=db_path, now=_NOW)
    assert status.reason_code == "JOB_DEGRADED"
    assert status.overall_status == "attention"
    assert status.consecutive_non_healthy == 1


def test_degraded_when_degradation_mode_set_even_if_synthesized(db_path: str) -> None:
    _insert_run(
        db_path,
        status="synthesized",
        generated_utc=(_NOW - timedelta(hours=1)).isoformat(),
        degradation="partial_context",
    )
    status = evaluate_daily_brief_job_health(db_path=db_path, now=_NOW)
    assert status.reason_code == "JOB_DEGRADED"


def test_stale(db_path: str) -> None:
    _insert_run(
        db_path, status="synthesized", generated_utc=(_NOW - timedelta(hours=72)).isoformat()
    )
    status = evaluate_daily_brief_job_health(db_path=db_path, now=_NOW)
    assert status.reason_code == "JOB_STALE"
    assert status.overall_status == "attention"


def test_run_read_only_by_default(db_path: str) -> None:
    _, agent_run_id = run_daily_brief_job_health(db_path=db_path, now=_NOW)
    assert agent_run_id is None


def test_emit_persists_metadata_only_v28_receipt(db_path: str) -> None:
    _insert_run(
        db_path, status="synthesized", generated_utc=(_NOW - timedelta(hours=1)).isoformat()
    )
    _, agent_run_id = run_daily_brief_job_health(db_path=db_path, now=_NOW, emit_receipt=True)
    assert agent_run_id is not None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(
        conn.execute(
            "SELECT * FROM second_brain_agent_run_receipts WHERE agent_id='daily_brief_job_health_agent'"
        ).fetchone()
    )
    conn.close()
    assert row["run_kind"] == "daily_brief_job_health"
    for col, value in row.items():
        if col.endswith("_persisted") or col == "external_writeback_performed":
            assert value == 0, f"guard {col} must be 0"


def test_proof_passes() -> None:
    proof = build_daily_brief_job_health_proof()
    assert proof["proof_passed"] is True
    assert proof["never_run_reason_code"] == "JOB_NEVER_RUN"
    assert proof["degraded_reason_code"] == "JOB_DEGRADED"
    assert proof["stale_reason_code"] == "JOB_STALE"
    assert proof["no_raw_content"] is True


def test_proof_has_no_forbidden_tokens() -> None:
    import json

    blob = json.dumps(build_daily_brief_job_health_proof(), default=str)
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob
