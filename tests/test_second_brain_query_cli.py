"""Phase 08A Prompt 08 — `second-brain query` CLI (offline, mock-first)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app

_REQUIRED_OUTPUT = (
    "answer_redacted",
    "source_refs",
    "confidence_labels",
    "review_tiers",
    "research_packet_summary",
    "evaluation_summary",
    "warnings",
    "advisory_vs_actionable_marking",
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_query_returns_required_output_fields(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "query", "what changed this week?", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    for field in _REQUIRED_OUTPUT:
        assert field in payload
    assert payload["advisory_vs_actionable_marking"]["disposition"] in {"advisory", "actionable"}
    assert payload["guardrails"]["tier_3_never_final_conclusion"] is True


def test_query_output_carries_no_raw_content(runner: CliRunner) -> None:
    out = runner.invoke(app, ["second-brain", "query", "summarize risk", "--json"]).output
    for forbidden in (
        "signed_url",
        "download_url",
        "raw_body",
        "raw_prompt",
        "raw_response",
        "secret",
    ):
        assert forbidden not in out


def test_query_help_lists_query(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "--help"])
    assert result.exit_code == 0
    assert "query" in result.output
