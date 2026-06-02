"""Phase 08B Prompt 04 — LaunchAgent scheduling + first-run-after-wake (read-only by default)."""

from __future__ import annotations

import plistlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.daily_brief.scheduling import (
    build_daily_brief_schedule_preview,
)
from hb_assistant.construction.second_brain.launchd_scheduler import (
    apply_launchd_install,
    build_launchd_scheduler_proof,
    evaluate_first_run_after_wake,
    evaluate_launchd_schedule,
    run_launchd_schedule_agent,
    uninstall_launchd,
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
    return str(tmp_path / "launchd.sqlite")


def _desired() -> tuple[str, int, int]:
    p = build_daily_brief_schedule_preview(emit=False)
    return p.label, p.hour, p.minute


def _write_plist(directory: Path, label: str, hour: int, minute: int) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{label}.plist"
    with path.open("wb") as f:
        plistlib.dump(
            {"Label": label, "StartCalendarInterval": {"Hour": hour, "Minute": minute}}, f
        )
    return path


def _insert_run(db_path: str, *, generated_utc: str, brief_date: str = "2026-06-02") -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO daily_brief_runs
            (brief_run_id, brief_date, mode, status, project_count, source_ref_count,
             review_required_count, stale_unknown_count, generated_utc)
        VALUES (?, ?, 'apply', 'completed', 0, 0, 0, 0, ?)
        """,
        (uuid.uuid4().hex, brief_date, generated_utc),
    )
    conn.commit()
    conn.close()


# --- schedule evaluation -------------------------------------------------------------------
def test_not_installed(tmp_path: Path) -> None:
    status = evaluate_launchd_schedule(launch_agents_dir=str(tmp_path / "LaunchAgents"))
    assert status.status == "not_installed"
    assert status.reason_code == "LAUNCHD_NOT_INSTALLED"
    assert status.plist_installed is False


def test_installed_ok(tmp_path: Path) -> None:
    label, hour, minute = _desired()
    la_dir = tmp_path / "LaunchAgents"
    _write_plist(la_dir, label, hour, minute)
    status = evaluate_launchd_schedule(launch_agents_dir=str(la_dir))
    assert status.status == "ok"
    assert status.reason_code == "LAUNCHD_INSTALLED_OK"
    assert status.installed_schedule == {"hour": hour, "minute": minute}


def test_schedule_drift(tmp_path: Path) -> None:
    label, hour, minute = _desired()
    la_dir = tmp_path / "LaunchAgents"
    _write_plist(la_dir, label, (hour + 3) % 24, minute)
    status = evaluate_launchd_schedule(launch_agents_dir=str(la_dir))
    assert status.status == "drift"
    assert status.reason_code == "SCHEDULE_DRIFT"


# --- first-run-after-wake catch-up ---------------------------------------------------------
def test_catch_up_needed_no_prior_run(db_path: str) -> None:
    ConstructionStore(db_path)
    status = evaluate_first_run_after_wake(db_path=db_path)
    assert status.status == "needed"
    assert status.reason_code == "CATCH_UP_NEEDED"
    assert status.last_run_date is None


def test_catch_up_not_needed_recent_run(db_path: str) -> None:
    ConstructionStore(db_path)
    _insert_run(db_path, generated_utc=datetime.now(timezone.utc).isoformat())
    status = evaluate_first_run_after_wake(db_path=db_path, now=datetime.now().replace(hour=23))
    assert status.status == "not_needed"
    assert status.reason_code == "CATCH_UP_NOT_NEEDED"


def test_catch_up_needed_after_wake(db_path: str) -> None:
    ConstructionStore(db_path)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    _insert_run(db_path, generated_utc=yesterday.isoformat())
    status = evaluate_first_run_after_wake(db_path=db_path, now=datetime.now().replace(hour=23))
    assert status.status == "needed"
    assert status.reason_code == "CATCH_UP_NEEDED"


def test_catch_up_stale(db_path: str) -> None:
    ConstructionStore(db_path)
    old = datetime.now(timezone.utc) - timedelta(days=10)
    _insert_run(db_path, generated_utc=old.isoformat())
    status = evaluate_first_run_after_wake(db_path=db_path, now=datetime.now().replace(hour=23))
    assert status.status == "stale"
    assert status.reason_code == "CATCH_UP_STALE"


# --- apply / uninstall: fail-closed by policy ----------------------------------------------
def test_apply_blocked_by_default_policy(tmp_path: Path) -> None:
    la_dir = tmp_path / "LaunchAgents"
    result = apply_launchd_install(confirm=True, launch_agents_dir=str(la_dir))
    assert result["status"] == "blocked"
    assert result["reason_code"] == "LAUNCHD_INSTALL_DISABLED_BY_POLICY"
    assert result["plist_written"] is False
    assert result["launchctl_invoked"] is False
    assert result["external_writeback_performed"] == 0
    assert not (la_dir / f"{_desired()[0]}.plist").exists()


def test_uninstall_blocked_by_default_policy(tmp_path: Path) -> None:
    result = uninstall_launchd(confirm=True, launch_agents_dir=str(tmp_path / "LaunchAgents"))
    assert result["status"] == "blocked"
    assert result["reason_code"] == "LAUNCHD_INSTALL_DISABLED_BY_POLICY"
    assert result["launchctl_invoked"] is False


def test_apply_requires_confirm_even_when_enabled(tmp_path: Path) -> None:
    result = apply_launchd_install(
        confirm=False, dry_run_install_only=False, launch_agents_dir=str(tmp_path / "LaunchAgents")
    )
    assert result["status"] == "blocked"
    assert result["detail"] == "confirm_required"


# --- apply / uninstall: real-write success path (override policy + temp dir + mock runner) --
def test_apply_success_with_override_policy(tmp_path: Path) -> None:
    label, hour, minute = _desired()
    la_dir = tmp_path / "LaunchAgents"
    log_dir = tmp_path / "logs"
    calls: list[list[str]] = []

    def fake_runner(args: list[str]) -> int:
        calls.append(args)
        return 0

    result = apply_launchd_install(
        confirm=True,
        dry_run_install_only=False,
        launch_agents_dir=str(la_dir),
        log_dir=str(log_dir),
        launchctl_runner=fake_runner,
    )
    assert result["status"] == "installed"
    assert result["plist_written"] is True
    assert result["launchctl_invoked"] is True
    assert result["external_writeback_performed"] == 0
    plist_path = la_dir / f"{label}.plist"
    assert plist_path.exists()
    # The real ~/Library/LaunchAgents was never touched.
    assert str(Path.home() / "Library" / "LaunchAgents") not in str(la_dir)
    assert calls and calls[0][:2] == ["launchctl", "load"]
    # A subsequent read sees the installed schedule on the policy time.
    follow = evaluate_launchd_schedule(launch_agents_dir=str(la_dir))
    assert follow.status == "ok"
    assert follow.installed_schedule == {"hour": hour, "minute": minute}


def test_uninstall_success_with_override_policy(tmp_path: Path) -> None:
    label, hour, minute = _desired()
    la_dir = tmp_path / "LaunchAgents"
    _write_plist(la_dir, label, hour, minute)
    calls: list[list[str]] = []

    result = uninstall_launchd(
        confirm=True,
        dry_run_install_only=False,
        launch_agents_dir=str(la_dir),
        launchctl_runner=lambda a: calls.append(a) or 0,
    )
    assert result["status"] == "uninstalled"
    assert result["plist_removed"] is True
    assert result["launchctl_invoked"] is True
    assert not (la_dir / f"{label}.plist").exists()
    assert calls and calls[0][:2] == ["launchctl", "unload"]


# --- agent run + receipt -------------------------------------------------------------------
def test_run_agent_read_only_by_default(db_path: str, tmp_path: Path) -> None:
    ConstructionStore(db_path)
    snapshot, agent_run_id = run_launchd_schedule_agent(
        db_path=db_path, launch_agents_dir=str(tmp_path / "LaunchAgents")
    )
    assert agent_run_id is None
    assert snapshot.overall_status == "attention"  # not installed + catch-up needed
    assert snapshot.schedule.reason_code == "LAUNCHD_NOT_INSTALLED"


def test_emit_persists_metadata_only_receipt(db_path: str, tmp_path: Path) -> None:
    ConstructionStore(db_path)
    _, agent_run_id = run_launchd_schedule_agent(
        db_path=db_path, launch_agents_dir=str(tmp_path / "LaunchAgents"), emit_receipt=True
    )
    assert agent_run_id is not None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM second_brain_agent_run_receipts").fetchone())
    conn.close()
    assert row["agent_id"] == "launchd_scheduler_agent"
    assert row["run_kind"] == "launchd_schedule_eval"
    for col, value in row.items():
        if col.endswith("_persisted") or col == "external_writeback_performed":
            assert value == 0, f"guard {col} must be 0"
    blob = " ".join(str(v) for v in row.values())
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob


# --- proof ---------------------------------------------------------------------------------
def test_proof_passes() -> None:
    proof = build_launchd_scheduler_proof()
    assert proof["proof_passed"] is True
    assert proof["schedule_reason_code"] == "LAUNCHD_NOT_INSTALLED"
    assert proof["install_blocked"]["reason_code"] == "LAUNCHD_INSTALL_DISABLED_BY_POLICY"
    assert proof["no_raw_content"] is True


def test_proof_has_no_forbidden_tokens() -> None:
    import json

    blob = json.dumps(build_launchd_scheduler_proof(), default=str)
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob
