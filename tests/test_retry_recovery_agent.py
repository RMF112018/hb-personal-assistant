"""Phase 08B Prompt 06 — retry/backoff receipts + Run Recovery Agent."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retry_recovery import (
    build_retry_recovery_proof,
    evaluate_retry,
    evaluate_run_recovery,
    plan_retry_schedule,
    read_latest_retry_receipts,
    record_retry_attempt,
    run_run_recovery_agent,
)
from hb_assistant.construction.second_brain.run_registry import acquire_run_lock, register_run
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

_BASE = datetime(2026, 6, 2, 5, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "retry.sqlite")


@pytest.fixture
def locks(tmp_path: Path) -> str:
    return str(tmp_path / "locks")


# --- retry / backoff -----------------------------------------------------------------------
def test_plan_retry_schedule() -> None:
    plan = plan_retry_schedule(run_kind="daily_brief")
    assert plan["max_attempts"] == 3
    assert plan["backoff_seconds"] == [60, 300, 900]
    assert len(plan["attempts"]) == 3


def test_evaluate_retry_scheduled() -> None:
    d = evaluate_retry(attempt_number=1, succeeded=False, now=_BASE)
    assert d.status == "scheduled"
    assert d.reason_code == "RETRY_SCHEDULED"
    assert d.backoff_seconds == 60
    assert d.next_attempt_utc


def test_evaluate_retry_exhausted() -> None:
    d = evaluate_retry(attempt_number=3, succeeded=False, now=_BASE)
    assert d.status == "exhausted"
    assert d.reason_code == "RETRY_EXHAUSTED"


def test_evaluate_retry_succeeded() -> None:
    d = evaluate_retry(attempt_number=2, succeeded=True, now=_BASE)
    assert d.status == "succeeded"
    assert d.reason_code == "RETRY_SUCCEEDED"


def test_record_retry_attempt_guard_zero(db_path: str) -> None:
    ConstructionStore(db_path)
    rid = record_retry_attempt(
        run_kind="daily_brief",
        attempt_number=1,
        max_attempts=3,
        outcome="failed",
        reason_code="RETRY_SCHEDULED",
        backoff_seconds=60,
        emit=True,
        db_path=db_path,
    )
    assert rid
    rows = read_latest_retry_receipts(db_path=db_path)
    assert len(rows) == 1 and rows[0]["outcome"] == "failed"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM second_brain_retry_receipts").fetchone())
    conn.close()
    for col, value in row.items():
        if col.endswith("_persisted") or col == "external_writeback_performed":
            assert value == 0, f"guard {col} must be 0"
    blob = " ".join(str(v) for v in row.values())
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob


def test_record_retry_attempt_off_by_default(db_path: str) -> None:
    ConstructionStore(db_path)
    assert (
        record_retry_attempt(
            run_kind="daily_brief",
            attempt_number=1,
            max_attempts=3,
            outcome="failed",
            reason_code="RETRY_SCHEDULED",
            db_path=db_path,
        )
        is None
    )


# --- run recovery --------------------------------------------------------------------------
def test_recovery_not_needed_when_no_orphans(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    status = evaluate_run_recovery(db_path=db_path, locks_dir=locks, now=_BASE)
    assert status.reason_code == "RECOVERY_NOT_NEEDED"
    assert status.overall_status == "ok"


def test_recovery_needed_with_orphan(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    register_run(run_kind="daily_brief", status="started", emit=True, db_path=db_path)
    status = evaluate_run_recovery(db_path=db_path, locks_dir=locks, now=_BASE)
    assert status.reason_code == "RECOVERY_NEEDED"
    assert status.orphan_count == 1


def test_recovery_blocked_by_live_lock(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    register_run(run_kind="daily_brief", status="started", emit=True, db_path=db_path)
    acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)  # live lock
    status = evaluate_run_recovery(db_path=db_path, locks_dir=locks, now=_BASE)
    assert status.reason_code == "RECOVERY_BLOCKED"


def test_recovery_dry_run_does_not_mutate(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    rid = register_run(run_kind="daily_brief", status="started", emit=True, db_path=db_path)
    status, agent_run_id = run_run_recovery_agent(
        mode="dry_run", db_path=db_path, locks_dir=locks, now=_BASE
    )
    assert status.dry_run is True
    assert status.recovered_count == 0
    conn = sqlite3.connect(db_path)
    st = conn.execute(
        "SELECT status FROM second_brain_run_registry WHERE run_registry_id = ?", (rid,)
    ).fetchone()[0]
    conn.close()
    assert st == "started"  # untouched in dry-run


def test_recovery_apply_recovers_orphan(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    rid = register_run(run_kind="daily_brief", status="started", emit=True, db_path=db_path)
    status, _ = run_run_recovery_agent(mode="apply", db_path=db_path, locks_dir=locks, now=_BASE)
    assert status.recovered_count == 1
    conn = sqlite3.connect(db_path)
    st = conn.execute(
        "SELECT status FROM second_brain_run_registry WHERE run_registry_id = ?", (rid,)
    ).fetchone()[0]
    conn.close()
    assert st == "recovered"


def test_recovery_emit_persists_v28_receipt(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    register_run(run_kind="daily_brief", status="started", emit=True, db_path=db_path)
    _, agent_run_id = run_run_recovery_agent(
        mode="apply", db_path=db_path, locks_dir=locks, now=_BASE, emit_receipt=True
    )
    assert agent_run_id is not None
    conn = sqlite3.connect(db_path)
    n = conn.execute(
        "SELECT COUNT(*) FROM second_brain_agent_run_receipts WHERE agent_id='run_recovery_agent'"
    ).fetchone()[0]
    conn.close()
    assert n == 1


# --- proof ---------------------------------------------------------------------------------
def test_proof_passes() -> None:
    proof = build_retry_recovery_proof()
    assert proof["proof_passed"] is True
    assert proof["retry_exhausted_reason_code"] == "RETRY_EXHAUSTED"
    assert proof["recovery_needed_reason_code"] == "RECOVERY_NEEDED"
    assert proof["recovered_count"] == 1
    assert proof["guard_columns_zero"] is True
    assert proof["no_raw_content"] is True


def test_proof_has_no_forbidden_tokens() -> None:
    import json

    blob = json.dumps(build_retry_recovery_proof(), default=str)
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob
