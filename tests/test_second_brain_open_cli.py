"""Phase 08B Prompt 12 — `second-brain automation open-brief / brief-status / receipts` CLI."""

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


def test_brief_status_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "brief-status", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation brief-status"
    assert "delivered" in payload and "opened" in payload
    assert payload["guardrails"]["no_external_delivery"] is True


def test_receipts_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "receipts", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation receipts"
    assert "receipt_count" in payload and isinstance(payload["receipts"], list)
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_open_brief_dry_run_default(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "open-brief", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation open-brief"
    assert payload["mode"] == "dry_run"
    assert payload["opened"] is False
    assert payload["agent_run_id"] is None


def test_open_brief_apply_fail_closed_on_default_seed(runner: CliRunner) -> None:
    # Default seed has daily_brief_open.open=false -> apply never opens. Fresh DB has no brief, so it
    # short-circuits to never-generated; either way no app is launched.
    _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "open-brief", "--mode", "apply", "--json"]
    )
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["opened"] is False
    assert payload["policy_open_enabled"] is False


def test_open_brief_invalid_mode(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "open-brief", "--mode", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "invalid_mode"


def test_open_brief_invalid_target(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "open-brief", "--target", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "invalid_target"
