"""Phase 08B Prompt 10 — `second-brain automation html-status / render-html` CLI."""

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


def test_html_status_read_only(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "html-status", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation html-status"
    assert payload["guardrails"]["self_contained_no_network"] is True
    assert payload["guardrails"]["no_raw_html_persisted"] is True
    assert payload["agent_run_id"] is None
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in result.output


def test_render_html_dry_run_default(runner: CliRunner) -> None:
    _migrate_active_db()
    result = runner.invoke(app, ["second-brain", "automation", "render-html", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain automation render-html"
    assert payload["mode"] == "dry_run"
    assert payload["render_status"] == "preview"
    assert payload["written"] is False
    assert payload["agent_run_id"] is None


def test_render_html_apply_skips_when_no_brief(runner: CliRunner) -> None:
    # A fresh migrated DB has no brief runs -> apply is a safe no-op (nothing rendered).
    _migrate_active_db()
    result = runner.invoke(
        app, ["second-brain", "automation", "render-html", "--mode", "apply", "--json"]
    )
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert payload["reason_code"] == "HTML_RENDER_NEVER_GENERATED"
    assert payload["render_status"] == "skipped"
    assert payload["written"] is False


def test_render_html_invalid_mode(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["second-brain", "automation", "render-html", "--mode", "bogus", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["error"] == "invalid_mode"
