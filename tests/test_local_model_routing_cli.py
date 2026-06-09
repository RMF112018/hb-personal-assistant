"""Phase 10 — CLI operator surfaces for local model eval/routing/intelligence (shape + exit codes)."""

from __future__ import annotations

import json
import pathlib

from typer.testing import CliRunner

from hb_assistant.cli.main import app

runner = CliRunner()

_RAW_PHRASES = ("Thread requests Bobby return", "shop-drawing transmittal")


def _assert_no_raw_leak(text: str) -> None:
    for phrase in _RAW_PHRASES:
        assert phrase not in text


def test_eval_help() -> None:
    result = runner.invoke(app, ["second-brain", "local-model", "eval", "--help"])
    assert result.exit_code == 0
    assert "decisive" in result.output.lower() or "evaluate" in result.output.lower()


def test_eval_synthetic_json_shape_and_exit_0() -> None:
    result = runner.invoke(
        app,
        ["second-brain", "local-model", "eval", "--suite", "daily-brief", "--models", "auto", "--synthetic", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    for key in ("ok", "applied", "dry_run", "models_attempted", "selected_profile", "blockers", "warnings", "metrics", "redaction_passed", "use_next_run", "recommendations"):
        assert key in payload, key
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["redaction_passed"] is True
    assert payload["use_next_run"]
    # Synthetic eval must be labelled as an offline CONTRACT check, not live model quality.
    assert payload["eval_mode"] == "synthetic_offline_contract"
    _assert_no_raw_leak(result.output)


def test_eval_unknown_suite_is_misuse_exit_2() -> None:
    result = runner.invoke(
        app, ["second-brain", "local-model", "eval", "--suite", "does-not-exist", "--task-family", "nope", "--json"]
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert any("no_fixtures" in b or "no_eligible" in b for b in payload["blockers"])


def test_eval_raw_fixtures_dir_inside_repo_refused_exit_2() -> None:
    repo_tests = str(pathlib.Path(__file__).resolve().parent)
    result = runner.invoke(
        app, ["second-brain", "local-model", "eval", "--raw-fixtures-dir", repo_tests, "--json"]
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert any("raw_fixture_refused" in b for b in payload["blockers"])


def test_route_and_profiles_json_shape() -> None:
    route = runner.invoke(
        app,
        ["second-brain", "local-model", "route", "--task-family", "daily_brief_synthesis_quality", "--mock", "--json"],
    )
    assert route.exit_code == 1  # daemon unreachable under --mock -> fail-closed
    rp = json.loads(route.output)
    assert rp["selected_profile"] == "brief_synthesis"
    assert rp["no_cloud"] is True

    profiles = runner.invoke(app, ["second-brain", "local-model", "profiles", "--mock", "--json"])
    assert profiles.exit_code == 0
    pp = json.loads(profiles.output)
    assert pp["ok"] is True
    assert pp["profiles"]


def test_eval_db_flag_is_ignored_with_warning(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["second-brain", "local-model", "eval", "--suite", "extraction", "--db", str(tmp_path / "x.sqlite"), "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert any("db_ignored" in w for w in payload["warnings"])
