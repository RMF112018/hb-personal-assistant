"""Phase 10 — local model profile router tests (hermetic, fail-closed, no cloud, no network)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.contracts import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.model_router import (
    RouterConfigError,
    build_profiles_report,
    load_local_model_task_routing,
    route_task_family,
)

runner = CliRunner()

_MISTRAL = "mistral-nemo:12b"
_QWEN = "qwen2.5:14b"


def test_routing_config_loads() -> None:
    routing = load_local_model_task_routing()
    assert routing.routes["daily_brief_synthesis_quality"] == "brief_synthesis"
    assert routing.guardrails.get("no_cloud") is True


def test_invalid_config_fails_closed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = tmp_path / "bad_routing.seed.yaml"
    bad.write_text("version: '1.0.0'\nroutes: {}\n", encoding="utf-8")  # empty routes -> invalid
    monkeypatch.setenv("HB_LOCAL_MODEL_TASK_ROUTING", str(bad))
    with pytest.raises(RouterConfigError):
        load_local_model_task_routing()


def test_unknown_task_family_is_blocked() -> None:
    result = route_task_family("does_not_exist", present_models={_MISTRAL})
    assert result.blocked is True
    assert result.reason_code == "unknown_task_family"
    assert result.selected_profile is None


def test_missing_model_produces_blocker() -> None:
    # Daemon reachable but no models installed -> fail closed, decision still reported.
    result = route_task_family("daily_brief_synthesis_quality", present_models=set())
    assert result.blocked is True
    assert result.reason_code == "no_available_local_model"
    assert result.selected_profile == "brief_synthesis"  # reported as the would-be primary


def test_daemon_unreachable_is_blocked() -> None:
    result = route_task_family("daily_brief_synthesis_quality", present_models=None)
    assert result.blocked is True
    assert result.reason_code == "daemon_unreachable"


def test_primary_route_when_model_present() -> None:
    result = route_task_family("daily_brief_synthesis_quality", present_models={_MISTRAL})
    assert result.blocked is False
    assert result.available is True
    assert result.selected_profile == "brief_synthesis"
    assert result.reason_code == "selected_routed"


def test_fallback_chain_selects_secondary() -> None:
    # relationship_scoring -> review_filter (qwen) with fallback default_extract (mistral).
    # Only mistral present -> primary missing -> fallback chosen.
    result = route_task_family("relationship_scoring", present_models={_MISTRAL})
    assert result.blocked is False
    assert result.selected_profile == "default_extract"
    assert result.reason_code == "selected_fallback"
    assert result.fallback_chain[0] == "review_filter"


def test_no_cloud_route_exists() -> None:
    result = route_task_family("daily_brief_synthesis_quality", present_models={_MISTRAL})
    assert result.no_cloud is True
    # Every routable profile is a local Ollama profile (no cloud provider anywhere).
    profiles = load_local_model_profiles()
    assert all(p.provider in {"ollama", "mock", "mlx", "llama_cpp"} for p in profiles.profiles)


def test_profiles_report_maps_task_families() -> None:
    report = build_profiles_report(present_models={_MISTRAL, _QWEN})
    by_id = {r["profile_id"]: r for r in report["profiles"]}
    assert "daily_brief_synthesis_quality" in by_id["brief_synthesis"]["task_families"]
    assert report["guardrails"]["no_cloud"] is True


def test_cli_route_json_shape_and_exit_code() -> None:
    # --mock => daemon unreachable => fail-closed blocked, exit 1, but full decision shape present.
    result = runner.invoke(
        app,
        ["second-brain", "local-model", "route", "--task-family", "daily_brief_synthesis_quality", "--mock", "--json"],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["task_family"] == "daily_brief_synthesis_quality"
    assert payload["selected_profile"] == "brief_synthesis"
    assert payload["no_cloud"] is True
    assert payload["blocked"] is True
    assert set(payload).issuperset({"ok", "applied", "dry_run", "blockers", "fallback_chain"})


def test_cli_route_unknown_family_exit_2() -> None:
    result = runner.invoke(
        app,
        ["second-brain", "local-model", "route", "--task-family", "bogus_family", "--mock", "--json"],
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["reason_code"] == "unknown_task_family"


def test_cli_profiles_json_shape() -> None:
    result = runner.invoke(app, ["second-brain", "local-model", "profiles", "--mock", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["profiles"]
    assert payload["guardrails"]["no_cloud"] is True
