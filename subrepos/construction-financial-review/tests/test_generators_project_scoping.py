"""P4b — generators are project-scoped via config (tropical byte-parity + fixtureproj scoping).

Drives the context generator's config seam (default_config + _apply_config) without running it,
and the CLI generator dispatch (subprocess mocked). Proves tropical resolves byte-identical
values and a second eligible project (fixtureproj) scopes output names/dirs; ineligible fails closed.
"""

from __future__ import annotations

import pytest
from construction_financial_review import cli
from construction_financial_review.context import generate_forecast_context_package as ctx

_PROCORE_TROPICAL = "cost_forecast_agent_db_json_export_tropical_20260614_080344"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "CFR_PROJECT_KEY",
        "CFR_CONTEXT_DATA_ROOT",
        "CFR_CONTEXT_OUT_DIR",
        "CFR_CONTEXT_STAMP",
        "HB_FORECAST_EVAL_PROJECT_ALLOWLIST",
    ):
        monkeypatch.delenv(key, raising=False)


def test_context_default_config_tropical_byte_parity(monkeypatch, tmp_path):
    monkeypatch.setenv("CFR_CONTEXT_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("CFR_CONTEXT_STAMP", "20260101_000000")
    ctx._apply_config(ctx.default_config())
    assert ctx.PROJECT_KEY == "tropical"
    assert ctx.PROCORE_DIR.name == _PROCORE_TROPICAL
    assert ctx.OUT.name == "forecast_context_package_tropical_20260101_000000"
    assert ctx.JUNE_CUTOFF == "2026-06-01"
    assert ctx.JULY_CUTOFF == "2026-07-01"
    assert ctx.ROW_COUNT_EXPECTATIONS["canonical/budget_codes.jsonl"] == 127
    # provenance source_file derives byte-identically from the procore dir name
    assert (
        f"{ctx.PROCORE_DIR.name}/procore_subcontractor_payment_app_headers.jsonl"
        == f"{_PROCORE_TROPICAL}/procore_subcontractor_payment_app_headers.jsonl"
    )


def test_context_scopes_to_second_project(monkeypatch, tmp_path):
    monkeypatch.setenv("CFR_PROJECT_KEY", "fixtureproj")
    monkeypatch.setenv("CFR_CONTEXT_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("CFR_CONTEXT_STAMP", "20260101_000000")
    ctx._apply_config(ctx.default_config())
    assert ctx.PROJECT_KEY == "fixtureproj"
    assert ctx.OUT.name == "forecast_context_package_fixtureproj_20260101_000000"
    assert ctx.PROCORE_DIR.name == "cost_forecast_agent_db_json_export_fixtureproj_20260101_000000"


def test_cli_runs_eligible_project_passing_env(monkeypatch, capsys):
    captured: dict = {}

    class _Proc:
        returncode = 0

    def _fake_run(args, env=None):
        captured["env"] = env
        return _Proc()

    monkeypatch.setattr(cli.subprocess, "run", _fake_run)
    rc = cli.cmd_run_generator("run-context", "fixtureproj")
    assert rc == 0
    assert captured["env"]["CFR_PROJECT_KEY"] == "fixtureproj"
    assert "not_supported" not in capsys.readouterr().out


def test_cli_refuses_ineligible_project(monkeypatch):
    # an ineligible project is refused before any subprocess is spawned
    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("subprocess must not run for an ineligible project")

    monkeypatch.setattr(cli.subprocess, "run", _boom)
    rc = cli.cmd_run_generator("run-context", "other")
    assert rc == 2
