"""Phase 08B Prompt 07 — `second-brain automation source-freshness / retrieval-freshness / observability`."""

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


def test_source_freshness_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "source-freshness", "--json"])
    assert result.exit_code in (0, 3), result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation source-freshness"
    assert payload["reason_code"]
    assert isinstance(payload["signals"], list) and payload["signals"]
    assert payload["guardrails"]["read_only"] is True
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_retrieval_freshness_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "retrieval-freshness", "--json"])
    assert result.exit_code in (0, 3), result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation retrieval-freshness"
    assert payload["reason_code"]


def test_observability_read_only_default(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "observability", "--json"])
    assert result.exit_code in (0, 3), result.output
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation observability"
    assert payload["reason_code"] in ("OBSERVABILITY_OK", "OBSERVABILITY_DEGRADED")
    assert payload["agent_run_id"] is None  # read-only by default
    assert "source" in payload and "runtime" in payload and "retrieval" in payload


def test_observability_emit_receipt_persists(runner: CliRunner) -> None:
    db_path = _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "observability", "--json", "--emit-receipt"]
    )
    assert result.exit_code in (0, 3), result.output
    payload = json.loads(result.output)
    assert payload["agent_run_id"]
    import sqlite3

    conn = sqlite3.connect(db_path)
    n = conn.execute(
        "SELECT COUNT(*) FROM second_brain_agent_run_receipts "
        "WHERE agent_id='freshness_observability_agent'"
    ).fetchone()[0]
    conn.close()
    assert n == 1
