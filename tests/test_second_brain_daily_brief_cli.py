"""Phase 08A Prompt 11 — ``second-brain daily-brief`` CLI."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_daily_brief_build_default_db_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "build", "--date", "2026-06-02", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["brief_date"] == "2026-06-02"
    assert "source_coverage" in payload
    assert "review_tier_counts" in payload
    assert payload["degradation_mode"] in {"none", "graceful_degraded", "blocked"}
    assert payload["delivery_handoff"]["output_format"] == "structured_data"
    assert payload["delivery_handoff"]["notification_emitted"] is False
    assert payload["guardrails"]["no_html_or_notifications"] is True


def test_daily_brief_build_invalid_mode_rejected(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "daily-brief",
            "build",
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


def test_daily_brief_triage_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "daily-brief", "triage", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "by_tier" in payload
    assert "tier_3_count" in payload
    assert payload["guardrails"]["model_direct_external_api_access"] is False


def test_daily_brief_output_carries_no_raw_content(runner: CliRunner) -> None:
    out = runner.invoke(
        app, ["second-brain", "daily-brief", "build", "--date", "2026-06-02", "--json"]
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


def test_daily_brief_packet_v2_top_level_self_identifying(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "daily-brief",
            "packet",
            "--date",
            "2026-06-06",
            "--version",
            "v2",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["packet_version"] == "DailyBriefHandoffPacketV2"
    assert "render_payload" in payload
    assert "governance_metadata" in payload


def test_daily_brief_v2_proof_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "v2-proof", "--no-evidence", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True


def test_daily_brief_rendered_proof_version_v2_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "daily-brief",
            "rendered-proof",
            "--version",
            "v2",
            "--no-evidence",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True


def test_daily_brief_output_receipt_proof_version_v2_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "daily-brief",
            "output-receipt-proof",
            "--version",
            "v2",
            "--no-evidence",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_passed"] is True


def test_daily_brief_rendered_proof_invalid_version_rejected(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "rendered-proof", "--version", "x", "--json"]
    )
    assert result.exit_code == 2, result.output


def test_daily_brief_v2_closeout_exit_zero(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "v2-closeout", "--no-evidence", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["closeout_complete"] is True
    assert payload["schema_version"] == 40
    assert payload["packet_version"] == "DailyBriefHandoffPacketV2"
