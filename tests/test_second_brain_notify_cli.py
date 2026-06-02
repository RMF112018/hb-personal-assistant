"""Phase 08B Prompt 11 — `second-brain automation notify-status / notify` CLI."""

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


def test_notify_status_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "notify-status", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation notify-status"
    assert payload["channel"] == "local_macos"
    assert payload["guardrails"]["fail_closed_emission"] is True
    assert payload["guardrails"]["no_external_delivery"] is True
    assert payload["agent_run_id"] is None
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_notify_dry_run_default(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "notify", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation notify"
    assert payload["mode"] == "dry_run"
    assert payload["agent_run_id"] is None


def test_notify_apply_disabled_by_policy_on_default_seed(runner: CliRunner) -> None:
    # Default seed has daily_brief_notification.emit=false, so apply must never emit. With a fresh DB
    # (no brief) it short-circuits to never-generated; either way no banner is fired.
    _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "notify", "--mode", "apply", "--json"]
    )
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["emitted"] is False
    assert payload["policy_emit_enabled"] is False
    assert payload["reason_code"] in ("NOTIFY_NEVER_GENERATED", "NOTIFY_DISABLED_BY_POLICY")


def test_notify_invalid_mode(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "notify", "--mode", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "invalid_mode"
