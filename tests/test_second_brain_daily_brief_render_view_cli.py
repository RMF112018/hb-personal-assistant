"""Phase 08B Prompt 01 — ``second-brain daily-brief render-view`` CLI (read-only)."""

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


def _seed_and_persist(runner: CliRunner) -> str:
    """Seed the active (isolated) DB and persist a brief run; return the brief_date."""
    db_path = str(PathPolicy().get_db_path())
    store = ConstructionStore(db_path)
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )
    gen = runner.invoke(
        app,
        [
            "second-brain",
            "daily-brief",
            "generate",
            "--date",
            "2026-06-02",
            "--project-key",
            "P1",
            "--emit-receipt",
            "--json",
        ],
    )
    assert gen.exit_code == 0, gen.output
    return "2026-06-02"


def test_render_view_by_date(runner: CliRunner) -> None:
    brief_date = _seed_and_persist(runner)
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "render-view", "--date", brief_date, "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["format"] == "render_view"
    assert payload["rendered"] is False
    assert payload["brief_date"] == brief_date
    assert [s["name"] for s in payload["sections"]] == [
        "what_matters_today",
        "priority_actions",
        "waiting_on",
        "meeting_prep",
        "file_review_queue",
        "project_signals",
    ]
    assert payload["guardrails"]["no_html_rendered"] is True
    for forbidden in (
        "raw_body",
        "raw_prompt",
        "raw_response",
        "signed_url",
        "download_url",
        "secret",
    ):
        assert forbidden not in result.output


def test_render_view_missing_selector_exit_2(runner: CliRunner) -> None:
    result = runner.invoke(app, ["second-brain", "daily-brief", "render-view", "--json"])
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "missing_selector"


def test_render_view_unknown_run_exit_4(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "daily-brief", "render-view", "--run-id", "nope", "--json"]
    )
    assert result.exit_code == 4, result.output
    assert json.loads(result.output)["error"] == "brief_run_not_found"
