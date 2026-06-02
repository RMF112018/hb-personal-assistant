"""Phase 08B Prompt 05 — `second-brain automation run-registry-status / run-lock-status / run-lock`."""

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


def test_run_registry_status_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "run-registry-status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation run-registry-status"
    assert "count" in payload and isinstance(payload["runs"], list)
    assert payload["guardrails"]["fail_closed_on_overlap"] is True
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_run_lock_status_absent_by_default(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "run-lock-status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation run-lock-status"
    assert payload["status"] in ("absent", "held", "stale")


def test_run_lock_dry_run_default(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "automation", "run-lock", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "dry_run"
    assert payload["acquire"]["status"] == "preview"
    assert payload["release"] is None


def test_run_lock_apply_cycle(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "run-lock", "--mode", "apply", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["acquire"]["status"] in ("acquired", "reclaimed")
    assert payload["release"]["status"] == "released"


def test_run_lock_invalid_mode(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "run-lock", "--mode", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "invalid_mode"
