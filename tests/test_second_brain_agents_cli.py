"""Phase 08A Prompt 02 Addendum — `second-brain agents` CLI (offline)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_agents_registry_lists_all(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "agents", "registry", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # 9 required Phase 08A agents + 4 Phase 10 local-agent-family entries.
    assert payload["count"] == 13
    assert len(payload["agents"]) == 13
    assert payload["guardrails"]["mcp_implemented"] is False
    ids = {a["agent_id"] for a in payload["agents"]}
    assert "second_brain_orchestrator_agent" in ids
    assert {
        "email_action_extraction_agent",
        "follow_up_watch_agent",
        "procore_digest_agent",
        "calendar_prep_agent",
    } <= ids
    for agent in payload["agents"]:
        assert agent["receipt_required"] is True
        assert agent["allowed_tool_groups"]


def test_agents_status_valid_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "agents", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["agent_count"] == 13
    assert payload["enabled_count"] == 13
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
