"""Phase 08B Prompt 04 — `second-brain automation launchd-*` / `catch-up-status` CLI."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _migrate_active_db() -> str:
    db_path = str(PathPolicy().get_db_path())
    ConstructionStore(db_path)
    return db_path


def test_launchd_status_reports_reason_codes(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "launchd-status", "--json"])
    assert result.exit_code in (0, 3), result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation launchd-status"
    assert payload["reason_code"]
    assert payload["schedule"]["reason_code"]
    assert payload["catch_up"]["reason_code"]
    assert payload["agent_run_id"] is None  # read-only by default
    assert payload["guardrails"]["dry_run_install_only"] is True
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_catch_up_status_advisory(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "catch-up-status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation catch-up-status"
    assert payload["reason_code"] in (
        "CATCH_UP_NEEDED",
        "CATCH_UP_NOT_NEEDED",
        "CATCH_UP_STALE",
    )


def test_launchd_install_preview_default(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "automation", "launchd-install", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "preview"
    assert payload["plist_written"] is False
    assert payload["launchctl_invoked"] is False


def test_launchd_install_apply_blocked_by_policy(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        ["second-brain", "automation", "launchd-install", "--apply", "--confirm", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "blocked"
    assert payload["reason_code"] == "LAUNCHD_INSTALL_DISABLED_BY_POLICY"
    assert payload["plist_written"] is False
    assert payload["launchctl_invoked"] is False
    assert payload["external_writeback_performed"] == 0


def test_launchd_uninstall_apply_blocked_by_policy(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        ["second-brain", "automation", "launchd-uninstall", "--apply", "--confirm", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "blocked"
    assert payload["reason_code"] == "LAUNCHD_INSTALL_DISABLED_BY_POLICY"
    assert payload["launchctl_invoked"] is False
