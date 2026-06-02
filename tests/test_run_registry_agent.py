"""Phase 08B Prompt 05 — no-overlap locking + run registry + run-step ledger."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.run_registry import (
    acquire_run_lock,
    build_run_registry_locking_proof,
    coordinate_no_overlap_run,
    finish_run,
    read_latest_run_registry,
    read_run_lock,
    read_run_steps,
    record_run_step,
    register_run,
    release_run_lock,
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

_BASE = datetime(2026, 6, 2, 5, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "run.sqlite")


@pytest.fixture
def locks(tmp_path: Path) -> str:
    return str(tmp_path / "locks")


# --- lock primitives -----------------------------------------------------------------------
def test_acquire_success(locks: str) -> None:
    res = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)
    assert res.status == "acquired"
    assert res.reason_code == "LOCK_ACQUIRED"
    assert res.token
    assert (Path(locks) / "morning_automation.lock").exists()
    # The lock lives outside the repo tree (temp dir injected here).
    assert "/hb-personal-assistant/" not in res.lock_path_redacted


def test_concurrent_acquire_blocked(locks: str) -> None:
    first = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)
    second = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)
    assert second.status == "blocked"
    assert second.reason_code == "RUN_OVERLAP_BLOCKED"
    # The live lock is NOT deleted or overwritten — the first token still releases it.
    rel = release_run_lock(token=str(first.token), locks_dir=locks)
    assert rel.status == "released"


def test_stale_lock_reclaimed(locks: str) -> None:
    acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)
    later = _BASE + timedelta(seconds=3601)  # past the 3600s default expiry
    res = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=later)
    assert res.status == "reclaimed"
    assert res.reason_code == "STALE_LOCK_RECLAIMED"
    assert res.prior_token_sha  # prior token recorded HASHED, never raw


def test_token_mismatch_release_blocked(locks: str) -> None:
    acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)
    res = release_run_lock(token="not-the-token", locks_dir=locks)
    assert res.status == "blocked"
    assert res.reason_code == "LOCK_RELEASE_TOKEN_MISMATCH"
    # The lock file is retained (diagnosable) after a refused release.
    assert (Path(locks) / "morning_automation.lock").exists()


def test_normal_completion_cleanup(locks: str) -> None:
    acq = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)
    rel = release_run_lock(token=str(acq.token), locks_dir=locks)
    assert rel.status == "released"
    assert not (Path(locks) / "morning_automation.lock").exists()


def test_dry_run_preview_writes_no_file(locks: str) -> None:
    res = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE, dry_run=True)
    assert res.status == "preview"
    assert not (Path(locks) / "morning_automation.lock").exists()


def test_read_lock_states(locks: str) -> None:
    assert read_run_lock(locks_dir=locks, now=_BASE).status == "absent"
    acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)
    assert read_run_lock(locks_dir=locks, now=_BASE).status == "held"
    assert read_run_lock(locks_dir=locks, now=_BASE + timedelta(seconds=3601)).status == "stale"


# --- registry + step ledger ----------------------------------------------------------------
def test_register_and_steps_persist_guard_zero(db_path: str) -> None:
    ConstructionStore(db_path)
    rid = register_run(
        run_kind="daily_brief",
        status="started",
        reason_code="RUN_REGISTERED",
        emit=True,
        db_path=db_path,
    )
    assert rid
    record_run_step(
        run_registry_id=rid,
        step_name="lock_acquire",
        step_order=0,
        status="acquired",
        reason_code="LOCK_ACQUIRED",
        db_path=db_path,
    )
    finish_run(
        run_registry_id=rid, status="completed", reason_code="RUN_REGISTERED", db_path=db_path
    )

    rows = read_latest_run_registry(db_path=db_path)
    assert len(rows) == 1 and rows[0]["step_count"] == 1 and rows[0]["status"] == "completed"
    steps = read_run_steps(rid, db_path=db_path)
    assert len(steps) == 1 and steps[0]["reason_code"] == "LOCK_ACQUIRED"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for table in ("second_brain_run_registry", "second_brain_run_steps"):
        row = dict(conn.execute(f"SELECT * FROM {table}").fetchone())
        for col, value in row.items():
            if col.endswith("_persisted") or col == "external_writeback_performed":
                assert value == 0, f"{table}.{col} guard must be 0"
    conn.close()


def test_register_off_by_default(db_path: str) -> None:
    ConstructionStore(db_path)
    assert register_run(run_kind="daily_brief", status="started", db_path=db_path) is None


def test_run_step_detail_rejects_forbidden_token(db_path: str) -> None:
    ConstructionStore(db_path)
    rid = register_run(run_kind="daily_brief", status="started", emit=True, db_path=db_path)
    with pytest.raises(ValueError):
        record_run_step(
            run_registry_id=str(rid),
            step_name="x",
            step_order=1,
            status="ok",
            detail="leaked raw_prompt here",
            db_path=db_path,
        )


# --- coordinator ---------------------------------------------------------------------------
def test_coordinator_happy_path(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    result = coordinate_no_overlap_run(
        run_kind="daily_brief",
        step_names=["store_readiness", "brief_generation"],
        locks_dir=locks,
        now=_BASE,
        emit=True,
        db_path=db_path,
    )
    assert result["status"] == "completed"
    assert result["reason_code"] == "RUN_REGISTRY_LOCKING_OK"
    assert result["run_registry_id"]
    # Lock acquired then released -> file gone.
    assert not (Path(locks) / "morning_automation.lock").exists()
    steps = read_run_steps(result["run_registry_id"], db_path=db_path)
    # lock_acquire + 2 declared steps
    assert {s["step_name"] for s in steps} == {
        "lock_acquire",
        "store_readiness",
        "brief_generation",
    }


def test_coordinator_blocked_on_live_lock(db_path: str, locks: str) -> None:
    ConstructionStore(db_path)
    acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=_BASE)  # hold the lock
    result = coordinate_no_overlap_run(
        run_kind="daily_brief",
        step_names=["x"],
        locks_dir=locks,
        now=_BASE,
        emit=True,
        db_path=db_path,
    )
    assert result["status"] == "blocked"
    assert result["reason_code"] == "RUN_OVERLAP_BLOCKED"
    assert result["run_registry_id"] is None


# --- proof ---------------------------------------------------------------------------------
def test_proof_passes() -> None:
    proof = build_run_registry_locking_proof()
    assert proof["proof_passed"] is True
    assert proof["overlap_blocked_reason_code"] == "RUN_OVERLAP_BLOCKED"
    assert proof["stale_reclaimed_reason_code"] == "STALE_LOCK_RECLAIMED"
    assert proof["token_mismatch_reason_code"] == "LOCK_RELEASE_TOKEN_MISMATCH"
    assert proof["guard_columns_zero"] is True
    assert proof["lock_outside_repo"] is True
    assert proof["no_raw_content"] is True


def test_proof_has_no_forbidden_tokens() -> None:
    import json

    blob = json.dumps(build_run_registry_locking_proof(), default=str)
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob
