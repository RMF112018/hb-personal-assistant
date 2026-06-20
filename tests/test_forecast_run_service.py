"""Service tests for the Forecast Run Center (Implementation Phase 3).

Unit tests inject a FAKE CFR workflow module into sys.modules so they never run the real
(heavy, subprocess-backed) generator — they exercise the service boundary: fail-closed config,
path/stamp redaction, run-record IO, and failure recording. A separate opt-in (integration-
marked) test runs the real chain against a configured live data_root.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.forecast_run_service import (
    ENV_CFR_SRC,
    ENV_DATA_ROOT,
    ENV_RUNS_ROOT,
    ForecastRunError,
    ForecastRunService,
)


# A workflow report shaped like the real one — deliberately full of paths + stamps to redact.
def _fake_report(**kwargs):
    stamp = kwargs["context_stamp"]
    return {
        "schema_version": 1,
        "project_key": "tropical",
        "mode": "file",
        "data_root": "/Users/bobbyfetting/Library/CloudStorage/live/2026-June",
        "work_root": str(kwargs["work_root"]),
        "context_stamp": stamp,
        "db_backed": False,
        "db_path": None,
        "context_package": f"/Users/bobbyfetting/x/forecast_context_package_tropical_{stamp}",
        "context_package_stamp": stamp,
        "analysis_package": "/Users/bobbyfetting/x/forecast_analysis_package_tropical_20260101_000000",
        "analysis_package_stamp": "20260101_000000",
        "chain_manifest": "/Users/bobbyfetting/x/forecast_package_chain_manifest.json",
        "safety_checks": {
            "project_key_supported": True,
            "data_root_is_dir": True,
            "work_root_outside_live_root": True,
            "explicit_context_stamp": True,
            "explicit_paths_only": True,
            "no_latest_glob": True,
            "db_path_required_for_db_mode": True,
            "db_path_rejected_in_file_mode": True,
        },
        "status": "ok",
        "report_path": "/Users/bobbyfetting/x/controlled_workflow_report.json",
    }


def _install_fake_workflow(monkeypatch: pytest.MonkeyPatch, fn) -> None:
    pkg = types.ModuleType("construction_financial_review")
    wf = types.ModuleType("construction_financial_review.workflows")
    mod = types.ModuleType(
        "construction_financial_review.workflows.controlled_db_context_analysis"
    )
    mod.run_controlled_context_analysis_workflow = fn  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "construction_financial_review", pkg)
    monkeypatch.setitem(sys.modules, "construction_financial_review.workflows", wf)
    monkeypatch.setitem(
        sys.modules,
        "construction_financial_review.workflows.controlled_db_context_analysis",
        mod,
    )


@pytest.fixture
def roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    data = tmp_path / "data"
    data.mkdir()
    runs = tmp_path / "runs"
    monkeypatch.setenv(ENV_DATA_ROOT, str(data))
    monkeypatch.setenv(ENV_RUNS_ROOT, str(runs))
    # CFR src exists in this repo; _ensure_cfr_importable will pass, then use the fake in sys.modules
    return data, runs


# -- happy path + redaction ---------------------------------------------------


def test_start_run_succeeds_redacted(roots, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_workflow(monkeypatch, _fake_report)
    svc = ForecastRunService()
    res = svc.start_run()
    assert res["status"] == "succeeded"
    assert res["packages"] == ["Context", "Analysis"]
    assert res["checks_total"] == 8 and res["checks_passed"] == 8
    assert res["validation_passed"] is True
    assert res["no_live_writes"] is True
    assert res["guardrails"]["no_live_db_write"] is True
    assert res["guardrails"]["no_live_data_root_write"] is True
    # the fake report was packed with /Users paths + stamps; none may survive into the payload
    assert find_redaction_leaks(res) == []
    assert res["display_label"].startswith("Context → analysis forecast")


def test_list_and_read_run(roots, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_workflow(monkeypatch, _fake_report)
    svc = ForecastRunService()
    created = svc.start_run()
    run_id = created["run_id"]
    listed = svc.list_runs()
    assert len(listed["runs"]) == 1
    assert listed["runs"][0]["run_id"] == run_id
    detail = svc.read_run(run_id)
    assert detail["run_id"] == run_id
    assert find_redaction_leaks(listed) == []
    assert find_redaction_leaks(detail) == []


def test_failed_run_recorded_without_leak(roots, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(**kwargs):
        # CFR errors embed live paths in their messages; the service must NOT surface them.
        raise RuntimeError("work_root is at/under the live forecast root: /Users/bobbyfetting/live")

    _install_fake_workflow(monkeypatch, _boom)
    svc = ForecastRunService()
    res = svc.start_run()
    assert res["status"] == "failed"
    assert res["packages"] == []
    assert "/Users/" not in (res.get("message") or "")
    assert find_redaction_leaks(res) == []
    # the failed run is still listed/readable
    assert svc.list_runs()["runs"][0]["status"] == "failed"


# -- fail-closed config -------------------------------------------------------


def test_data_root_unset_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DATA_ROOT, raising=False)
    monkeypatch.setenv(ENV_RUNS_ROOT, str(tmp_path / "runs"))
    with pytest.raises(ForecastRunError):
        ForecastRunService().start_run()


def test_data_root_missing_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DATA_ROOT, str(tmp_path / "nope"))
    monkeypatch.setenv(ENV_RUNS_ROOT, str(tmp_path / "runs"))
    with pytest.raises(ForecastRunError):
        ForecastRunService().start_run()


def test_runs_root_unset_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data))
    monkeypatch.delenv(ENV_RUNS_ROOT, raising=False)
    with pytest.raises(ForecastRunError):
        ForecastRunService().list_runs()


def test_runs_root_under_data_root_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data))
    monkeypatch.setenv(ENV_RUNS_ROOT, str(data / "runs"))  # under the source root
    _install_fake_workflow(monkeypatch, _fake_report)
    with pytest.raises(ForecastRunError):
        ForecastRunService().start_run()


def test_cfr_src_missing_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data))
    monkeypatch.setenv(ENV_RUNS_ROOT, str(tmp_path / "runs"))
    monkeypatch.setenv(ENV_CFR_SRC, str(tmp_path / "no-such-cfr-src"))
    with pytest.raises(ForecastRunError):
        ForecastRunService().start_run()


def test_unknown_run_id(roots) -> None:
    with pytest.raises(ForecastRunError, match="unknown run_id"):
        ForecastRunService().read_run("does-not-exist")


# -- opt-in real generation (not in the default suite) ------------------------


@pytest.mark.integration
def test_real_generation_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs the REAL context->analysis chain against the configured live data_root.

    Skipped unless HB_FORECAST_DATA_ROOT points to a real source root. Proves the live data
    root is not mutated and no live writes occur.
    """
    import os

    live = os.environ.get(ENV_DATA_ROOT)
    if not live or not Path(live).is_dir():
        pytest.skip("HB_FORECAST_DATA_ROOT not set to a real source root")
    runs = tmp_path / "runs"
    monkeypatch.setenv(ENV_RUNS_ROOT, str(runs))
    res = ForecastRunService().start_run()
    assert res["status"] == "succeeded"
    assert res["no_live_writes"] is True
    assert find_redaction_leaks(res) == []
