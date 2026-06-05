"""Phase 08A Prompt 02 Addendum — `second-brain agents` CLI (offline)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_agents_registry_lists_nine(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "agents", "registry", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["count"] == 9
    assert len(payload["agents"]) == 9
    assert payload["guardrails"]["mcp_implemented"] is False
    ids = {a["agent_id"] for a in payload["agents"]}
    assert "second_brain_orchestrator_agent" in ids
    for agent in payload["agents"]:
        assert agent["receipt_required"] is True
        assert agent["allowed_tool_groups"]


def test_agents_status_valid_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "agents", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["agent_count"] == 9
    assert payload["enabled_count"] == 9
    assert payload["registry_valid"] is True
    assert payload["tool_policy_valid"] is True
    assert payload["violations_count"] == 0
    assert payload["tier3_handling_visible"] is True
    assert payload["guardrails"]["mcp_implemented"] is False
    assert payload["contracts"]["agent_registry_contract"].startswith("phase_08a_agent_registry")


def test_agents_output_carries_no_raw_content(runner: CliRunner) -> None:
    out = runner.invoke(app, ["second-brain", "agents", "registry", "--json"]).output
    out += runner.invoke(app, ["second-brain", "agents", "status", "--json"]).output
    for forbidden in (
        "signed_url",
        "download_url",
        "raw_body",
        "raw_prompt",
        "raw_response",
        "token",
        "secret",
    ):
        assert forbidden not in out


def test_root_help_lists_second_brain(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "second-brain" in result.output
