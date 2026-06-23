"""Phase P3 — DB-native model input accessors (run-service routing + flag logic).

Proves the forecast Run Center can source the three covered source domains (budget_details,
cost_entries, monthly_actuals) from a NON-LIVE v59 DB by routing ``forecast_run_service.start_run``
through the existing CFR controlled workflow in ``db`` mode, behind the default-off flag
``HB_FORECAST_DB_BACKED_INPUTS_ENABLED``:

  - flag default OFF; resolves explicit > env > settings-file;
  - flag OFF  -> mode="file", no db_path (byte-identical to today; ambient db env ignored);
  - flag ON   -> mode="db" with the resolved NON-LIVE db_path threaded into the workflow;
  - fail-closed BEFORE the workflow when the flag is on but the db_path is the live/default DB,
    or no db_path resolves at all (recorded as a failed run; the workflow is never called);
  - no_live_writes holds in db mode (work-root outside the live root).

The underlying file-vs-DB *package parity* of the DB-read machinery is proven independently in
tests/test_forecast_context_runner_phase6.py; this module deliberately spies on the workflow to
isolate the run-service routing logic (no subprocess, no live DB, nothing under the live root).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics import forecast_run_service as svc
from hb_assistant.construction.analytics import forecast_runtime_config as cfg

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review.workflows import (  # noqa: E402
    controlled_db_context_analysis as cdca,
)

_ENV_FLAG = "HB_FORECAST_DB_BACKED_INPUTS_ENABLED"
_ENV_DB_PATH = "HB_FORECAST_DB_PATH"
_ENV_DATA_ROOT = "HB_FORECAST_DATA_ROOT"
_ENV_RUNS_ROOT = "HB_FORECAST_RUNS_ROOT"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """No ambient forecast env leaks into a controlled run unless a test sets it explicitly."""
    for name in (_ENV_FLAG, _ENV_DB_PATH, _ENV_DATA_ROOT, _ENV_RUNS_ROOT):
        monkeypatch.delenv(name, raising=False)


class _Spy:
    """Records the workflow kwargs and returns a synthetic no-live report (no real generation)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, *, data_root, work_root, context_stamp, mode, db_path=None, project_key, **_):
        self.calls.append({"mode": mode, "db_path": db_path, "project_key": project_key})
        return {
            "mode": mode,
            "db_backed": mode == "db",
            "db_path": str(db_path) if db_path else None,
            "context_package": str(Path(work_root) / mode / "ctx"),
            "analysis_package": str(Path(work_root) / mode / "ana"),
            "safety_checks": {
                "work_root_outside_live_root": True,
                "data_root_is_dir": True,
                "project_key_supported": True,
            },
            "status": "ok",
        }


def _service(tmp_path: Path) -> svc.ForecastRunService:
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    runs_root = tmp_path / "runs"  # sibling of data_root (never under it)
    return svc.ForecastRunService(data_root=str(data_root), runs_root=str(runs_root))


def _record(tmp_path: Path, run_id: str) -> dict:
    path = tmp_path / "runs" / run_id / "run_record.json"
    return json.loads(path.read_text(encoding="utf-8"))


# --- 1. flag resolution ----------------------------------------------------------------


def test_flag_defaults_off_and_resolves_env_and_explicit(monkeypatch):
    monkeypatch.delenv(_ENV_FLAG, raising=False)
    assert cfg.resolve_db_backed_inputs_enabled() is False
    monkeypatch.setenv(_ENV_FLAG, "1")
    assert cfg.resolve_db_backed_inputs_enabled() is True
    monkeypatch.setenv(_ENV_FLAG, "0")
    assert cfg.resolve_db_backed_inputs_enabled() is False
    # explicit overrides env
    assert cfg.resolve_db_backed_inputs_enabled(True) is True


def test_flag_surfaced_in_runtime_status():
    status = cfg.build_runtime_status()
    assert status["db_backed_inputs"]["enabled"] in (True, False)


# --- 2. routing: flag OFF -> file mode -------------------------------------------------


def test_flag_off_routes_file_mode(tmp_path, monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(cdca, "run_controlled_context_analysis_workflow", spy)
    monkeypatch.delenv(_ENV_FLAG, raising=False)
    out = _service(tmp_path).start_run()
    assert out["status"] == "succeeded"
    assert out["no_live_writes"] is True
    assert len(spy.calls) == 1
    assert spy.calls[0]["mode"] == "file"
    assert spy.calls[0]["db_path"] is None
    assert _record(tmp_path, out["run_id"])["mode"] == "file"


def test_file_mode_ignores_ambient_db_path(tmp_path, monkeypatch):
    """Flag OFF: an ambient HB_FORECAST_DB_PATH must NOT pull the run into db mode."""
    spy = _Spy()
    monkeypatch.setattr(cdca, "run_controlled_context_analysis_workflow", spy)
    monkeypatch.delenv(_ENV_FLAG, raising=False)
    monkeypatch.setenv(_ENV_DB_PATH, str(tmp_path / "ambient_v59.db"))
    out = _service(tmp_path).start_run()
    assert out["status"] == "succeeded"
    assert spy.calls[0]["mode"] == "file"
    assert spy.calls[0]["db_path"] is None


# --- 3. routing: flag ON + non-live db_path -> db mode ---------------------------------


def test_flag_on_routes_db_mode_with_nonlive_db(tmp_path, monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(cdca, "run_controlled_context_analysis_workflow", spy)
    db = tmp_path / "v59.db"
    monkeypatch.setenv(_ENV_FLAG, "1")
    monkeypatch.setenv(_ENV_DB_PATH, str(db))
    out = _service(tmp_path).start_run()
    assert out["status"] == "succeeded"
    assert out["no_live_writes"] is True
    assert len(spy.calls) == 1
    assert spy.calls[0]["mode"] == "db"
    assert spy.calls[0]["db_path"] == db
    rec = _record(tmp_path, out["run_id"])
    assert rec["mode"] == "db"
    assert rec["no_live_writes"] is True


# --- 4. fail-closed: flag ON but db_path is live / unconfigured -------------------------


def test_flag_on_live_db_path_fails_closed(tmp_path, monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(cdca, "run_controlled_context_analysis_workflow", spy)
    monkeypatch.setenv(_ENV_FLAG, "1")
    monkeypatch.setenv(_ENV_DB_PATH, str(PathPolicy().get_db_path()))  # the LIVE/default DB
    out = _service(tmp_path).start_run()
    assert out["status"] == "failed"
    assert spy.calls == []  # never reached the workflow
    assert "ForecastRunError" in (out.get("message") or "")
    assert out["no_live_writes"] is True


def test_flag_on_unconfigured_db_path_fails_closed(tmp_path, monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(cdca, "run_controlled_context_analysis_workflow", spy)
    monkeypatch.setenv(_ENV_FLAG, "1")
    # Force resolution to yield no db_path at all (no managed-default fallback).
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.forecast_runtime_config.resolve_db_path",
        lambda *a, **k: None,
    )
    out = _service(tmp_path).start_run()
    assert out["status"] == "failed"
    assert spy.calls == []
    assert "ForecastRunError" in (out.get("message") or "")
