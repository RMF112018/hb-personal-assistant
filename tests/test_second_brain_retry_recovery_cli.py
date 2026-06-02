"""Phase 08B Prompt 06 — `second-brain automation retry-plan / run-recovery` CLI."""

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


def test_retry_plan_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "retry-plan", "--run-kind", "daily_brief", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation retry-plan"
    assert payload["max_attempts"] == 3
    assert len(payload["attempts"]) == 3
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_run_recovery_dry_run_default(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "run-recovery", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation run-recovery"
    assert payload["mode"] == "dry_run"
    assert payload["dry_run"] is True
    # Fresh DB -> no orphaned runs.
    assert payload["reason_code"] == "RECOVERY_NOT_NEEDED"
    assert payload["agent_run_id"] is None


def test_run_recovery_apply(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "run-recovery", "--mode", "apply", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["dry_run"] is False


def test_run_recovery_invalid_mode(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "run-recovery", "--mode", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "invalid_mode"
