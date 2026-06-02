"""Phase 08A Prompt 06 — `second-brain query-tools` CLI (offline, read-only)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_query_tools_list_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "query-tools", "list", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 13
    assert payload["policy_valid"] is True
    assert payload["backed_count"] >= 1
    assert payload["guardrails"]["no_arbitrary_sql"] is True
    assert payload["guardrails"]["read_only"] is True
    names = {t["tool_name"] for t in payload["tools"]}
    assert "risk_digest" in names and "accepted_relationships" in names


def test_query_tools_run_unbacked_tool_exit_zero(runner: CliRunner) -> None:
    # project_context has no read-model and does not touch the DB (emit_receipt off).
    result = runner.invoke(
        app, ["second-brain", "query-tools", "run", "project_context", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["tool"] == "project_context"
    assert payload["status"] == "no_read_model"
    assert payload["row_count"] == 0


def test_query_tools_run_unknown_tool_rejected(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "query-tools", "run", "DROP TABLE x", "--json"]
    )
    assert result.exit_code == 3, result.output
    payload = json.loads(result.output)
    assert payload["error"] == "tool_not_allowlisted"


def test_query_tools_output_carries_no_raw_content(runner: CliRunner) -> None:
    out = runner.invoke(app, ["second-brain", "query-tools", "list", "--json"]).output
    for forbidden in ("signed_url", "download_url", "raw_body", "raw_prompt", "raw_response"):
        assert forbidden not in out
