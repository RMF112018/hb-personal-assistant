"""Phase 08B Prompt 08 — `second-brain automation daily-brief-health` CLI."""

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


def test_daily_brief_health_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "daily-brief-health", "--json"])
    assert result.exit_code in (0, 3), result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation daily-brief-health"
    assert payload["reason_code"] in ("JOB_HEALTHY", "JOB_DEGRADED", "JOB_STALE", "JOB_NEVER_RUN")
    assert payload["agent_run_id"] is None  # read-only by default
    assert payload["guardrails"]["read_only"] is True
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_daily_brief_health_emit_receipt_persists(runner: CliRunner) -> None:
    db_path = _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "daily-brief-health", "--json", "--emit-receipt"]
    )
    assert result.exit_code in (0, 3), result.output
    payload = json.loads(result.output)
    assert payload["agent_run_id"]
    import sqlite3

    conn = sqlite3.connect(db_path)
    n = conn.execute(
        "SELECT COUNT(*) FROM second_brain_agent_run_receipts "
        "WHERE agent_id='daily_brief_job_health_agent'"
    ).fetchone()[0]
    conn.close()
    assert n == 1
