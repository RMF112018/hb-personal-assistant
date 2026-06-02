"""Phase 08A Prompt 13 — launchd scheduling dry-run install preview."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.daily_brief import (
    build_daily_brief_schedule_preview,
    build_launchd_schedule_proof,
    read_latest_launchd_schedule_previews,
)
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "schedule.sqlite")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_preview_structure(db_path: str) -> None:
    ConstructionStore(db_path)
    preview = build_daily_brief_schedule_preview(db_path=db_path, emit=False)
    assert preview.label == "com.hb.personal-assistant.second-brain-daily-brief"
    assert (preview.hour, preview.minute) == (20, 0)
    assert preview.day_offset == 1
    assert preview.command_mode == "apply"
    assert preview.dry_run_install_only is True
    assert preview.external_writeback_performed is False
    assert preview.logs_outside_repo is True
    assert preview.preview_id is None  # not emitted
    args = preview.program_arguments_redacted
    assert "generate" in args and "--mode" in args and "--day-offset" in args
    assert "--emit-receipt" in args
    assert preview.plist["StartCalendarInterval"] == {"Hour": 20, "Minute": 0}


def test_preview_paths_are_redacted(db_path: str) -> None:
    ConstructionStore(db_path)
    preview = build_daily_brief_schedule_preview(db_path=db_path, emit=False)
    home = str(Path.home())
    blob = preview.model_dump_json()
    assert home not in blob  # $HOME redacted to ~
    assert preview.plist_path_redacted.startswith("~/Library/LaunchAgents/")


def test_emit_persists_dry_run_row_guard_zero(db_path: str) -> None:
    ConstructionStore(db_path)
    preview = build_daily_brief_schedule_preview(db_path=db_path, emit=True)
    assert preview.preview_id

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM launchd_schedule_previews").fetchone())
    conn.close()

    assert row["mode"] == "dry_run"  # table CHECK forbids anything else
    assert row["label"] == preview.label
    assert row["plist_path_redacted"]
    assert row["log_dir_redacted"]
    assert row["external_writeback_performed"] == 0

    latest = read_latest_launchd_schedule_previews(db_path=db_path)
    assert latest and latest[0]["launchd_preview_id"] == preview.preview_id


def test_table_rejects_non_dry_run_mode(db_path: str) -> None:
    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO launchd_schedule_previews "
            "(launchd_preview_id, mode, label, schedule_json) VALUES ('x','apply','l','{}')"
        )
    conn.close()


def test_proof_passes() -> None:
    proof = build_launchd_schedule_proof()
    assert proof["proof_passed"] is True
    assert proof["mode_is_dry_run"] is True
    assert proof["guard_column_zero"] is True
    assert proof["logs_outside_repo"] is True
    assert proof["no_plist_written"] is True
    assert proof["no_secrets_or_home_leak"] is True


def test_cli_schedule_preview_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "daily-brief", "schedule-preview", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    assert payload["dry_run_install_only"] is True
    assert payload["logs_outside_repo"] is True
    assert payload["guardrails"]["no_launchctl_invocation"] is True
    assert payload["guardrails"]["no_plist_written"] is True
    assert payload["command_mode"] == "apply"
    assert payload["schedule"] == {"hour": 20, "minute": 0}


def test_cli_generate_day_offset_defaults_date(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "generate", "--day-offset", "1", "--json"]
    )
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    expected = (date.today() + timedelta(days=1)).isoformat()
    assert payload["brief_date"] == expected
    assert payload["mode"] == "dry_run"
