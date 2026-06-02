"""Phase 08B Prompt 09 — `second-brain automation delivery-status / deliver` CLI."""

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


def test_delivery_status_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "delivery-status", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation delivery-status"
    assert payload["delivery_channel"] == "obsidian_vault"
    assert payload["guardrails"]["no_external_delivery"] is True
    assert payload["agent_run_id"] is None
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_deliver_dry_run_default(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "deliver", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation deliver"
    assert payload["mode"] == "dry_run"
    assert payload["delivery_status"] == "preview"
    assert payload["written"] is False
    # Off-by-default V28 receipt.
    assert payload["agent_run_id"] is None


def test_deliver_apply_skips_when_no_brief(runner: CliRunner) -> None:
    # A fresh migrated DB has no brief runs -> apply is a safe no-op (nothing delivered).
    _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "deliver", "--mode", "apply", "--json"]
    )
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["reason_code"] == "DELIVERY_NEVER_GENERATED"
    assert payload["delivery_status"] == "skipped"
    assert payload["written"] is False


def test_deliver_invalid_mode(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "deliver", "--mode", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "invalid_mode"
