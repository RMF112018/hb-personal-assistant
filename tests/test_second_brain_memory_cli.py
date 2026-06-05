"""Phase 08A Prompt 10 — `second-brain memory` + `preference` CLI (offline, dry-run)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_memory_candidate_sensitive_routes_tier_3(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "memory",
            "candidate",
            "--statement",
            "alleged claim entitlement",
            "--memory-type",
            "claim",
            "--origin-id",
            "qr-1",
            "--confidence",
            "high",
            "--sensitivity",
            "financial",
            "--source-refs",
            "cross_source_relationships:rel-1",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    c = payload["candidate"]
    assert c["review_tier"] == 3
    assert c["review_tier_reason_code"] == "T3_SENSITIVE_HIGH_IMPACT"
    assert c["review_required"] is True
    assert payload["emitted"] is False  # dry-run default


def test_memory_review_missing_candidate_exit_3(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "memory",
            "review",
            "--candidate-id",
            "does-not-exist",
            "--decision",
            "accepted",
            "--json",
        ],
    )
    assert result.exit_code == 3, result.output
    assert json.loads(result.output)["error"] == "candidate_not_found"


def test_preference_capture_sensitive_tier_3(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "second-brain",
            "preference",
            "capture",
            "--key",
            "personnel_emphasis",
            "--value",
            "[redacted]",
            "--type",
            "personnel",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    p = json.loads(result.output)["preference"]
    assert p["review_tier"] == 3
    assert p["review_status"] == "pending_review"


def test_memory_cli_output_no_raw_content(runner: CliRunner) -> None:
    out = runner.invoke(
        app,
        [
            "second-brain",
            "memory",
            "candidate",
            "--statement",
            "x",
            "--origin-id",
            "o",
            "--source-refs",
            "f:r",
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
