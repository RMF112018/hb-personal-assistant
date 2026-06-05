"""Phase 08A Prompt 07 — `second-brain research-packet` CLI (offline, read-only)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_research_packet_build_default_db_exit_zero(runner: CliRunner) -> None:
    # Against the (empty/local) DB the packet blocks gracefully; the command still exits 0.
    result = runner.invoke(
        app,
        [
            "second-brain",
            "research-packet",
            "build",
            "--packet-type",
            "interactive_query",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["packet_type"] == "interactive_query"
    assert payload["request_requires_packet"] is True
    assert "synthesis_allowed" in payload
    assert payload["packet"]["degradation_mode"] in {"none", "graceful_degraded", "blocked"}
    assert payload["guardrails"]["synthesis_requires_packet"] is True


def test_research_packet_build_daily_brief(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "research-packet", "build", "--packet-type", "daily_brief", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["packet_type"] == "daily_brief"
    assert payload["request_requires_packet"] is True


def test_research_packet_build_invalid_packet_type_rejected(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "research-packet", "build", "--packet-type", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["error"] == "invalid_packet_type"


def test_research_packet_output_carries_no_raw_content(runner: CliRunner) -> None:
    out = runner.invoke(
        app,
        [
            "second-brain",
            "research-packet",
            "build",
            "--packet-type",
            "interactive_query",
            "--json",
        ],
    ).output
    for forbidden in (
        "signed_url",
        "download_url",
        "raw_body",
        "raw_prompt",
        "raw_response",
        "secret",
    ):
        assert forbidden not in out
