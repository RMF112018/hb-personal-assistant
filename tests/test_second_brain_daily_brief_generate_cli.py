"""Phase 08A Prompt 12 — ``second-brain daily-brief generate`` CLI."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_generate_dry_run_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "generate", "--date", "2026-06-02", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "dry_run"
    assert payload["applied"] is False  # dry-run never applies
    assert "evaluation" in payload
    assert payload["delivery_handoff"]["local_only"] is True
    assert payload["delivery_handoff"]["external_delivery_performed"] is False
    assert payload["delivery_handoff"]["html_rendering"]["rendered"] is False
    assert payload["delivery_handoff"]["notification_summary"]["emitted"] is False
    assert payload["guardrails"]["apply_blocked_when_evaluation_fails"] is True
    assert payload["guardrails"]["no_external_delivery"] is True


def test_generate_invalid_mode_rejected(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "daily-brief",
            "generate",
            "--date",
            "2026-06-02",
            "--mode",
            "bogus",
            "--json",
        ],
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["error"] == "invalid_mode"


def test_generate_output_carries_no_raw_content(runner: CliRunner) -> None:
    out = runner.invoke(
        app, ["second-brain", "daily-brief", "generate", "--date", "2026-06-02", "--json"]
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
