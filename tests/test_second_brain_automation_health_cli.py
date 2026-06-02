"""Phase 08B Prompt 03 — `second-brain automation health` CLI (read-only status surface)."""

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
    """Migrate the isolated (autouse) app-support DB to LATEST so health is OK."""
    db_path = str(PathPolicy().get_db_path())
    ConstructionStore(db_path)
    return db_path


def test_health_healthy_exit_zero(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "health", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation health"
    assert payload["overall_status"] == "ok"
    assert payload["reason_code"] == "RUN_OK"
    assert payload["agent_run_id"] is None  # read-only by default
    assert payload["guardrails"]["read_only"] is True
    assert payload["guardrails"]["no_external_delivery"] is True
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_health_degraded_exit_three(runner: CliRunner) -> None:
    # Fresh isolated DB (unmigrated) -> degraded health -> exit 3 with actionable reason codes.
    result = runner.invoke(app, ["second-brain", "automation", "health", "--json"])
    assert result.exit_code == 3, result.output
    payload = json.loads(result.output)
    assert payload["overall_status"] == "degraded"
    assert payload["reason_code"] == "RUN_DEGRADED"
    assert payload["degraded_checks"]


def test_health_emit_receipt_persists(runner: CliRunner) -> None:
    db_path = _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "health", "--json", "--emit-receipt"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["agent_run_id"]
    import sqlite3

    conn = sqlite3.connect(db_path)
    n = conn.execute(
        "SELECT COUNT(*) FROM second_brain_agent_run_receipts WHERE agent_id='automation_health_agent'"
    ).fetchone()[0]
    assert n == 1
