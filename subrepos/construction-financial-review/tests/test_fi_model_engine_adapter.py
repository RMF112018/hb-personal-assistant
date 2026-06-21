"""Tests for the model-engine adapter subprocess boundary + the runtime-backed shadow artifacts.

Uses a deterministic stub runner (no statsforecast) invoked through sys.executable, so the boundary
is fully exercised on Python 3.14 with no isolated venv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_intelligence import (
    generate_forecast_intelligence_package as gen,
)
from construction_financial_review.forecast_intelligence import model_engine_adapter as mea

STUB = str(Path(__file__).resolve().parent / "_stub_model_engine_runner.py")

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
_HAS_DATA = (
    DATA_ROOT.is_dir()
    and list(DATA_ROOT.glob("forecast_analysis_package_tropical_crosswalk_v2_*"))
    and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for v in (mea.ENV_PYTHON, mea.ENV_RUNNER, mea.ENV_PROBE_IMPORT):
        monkeypatch.delenv(v, raising=False)


# --------------------------------------------------------------------------- available()


def test_available_not_configured(monkeypatch):
    assert mea.available() == (False, "not_configured")


def test_available_interpreter_not_found(monkeypatch):
    monkeypatch.setenv(mea.ENV_PYTHON, "/no/such/python")
    ok, reason = mea.available()
    assert ok is False and reason == "interpreter_not_found"


def test_available_import_probe_fails_for_statsforecast(monkeypatch):
    # Real default probe is statsforecast, absent on the 3.14 interpreter.
    monkeypatch.setenv(mea.ENV_PYTHON, sys.executable)
    monkeypatch.setenv(mea.ENV_RUNNER, STUB)
    ok, reason = mea.available()
    assert ok is False and reason == "statsforecast_import_failed"


def test_available_ok_with_probe_override(monkeypatch):
    monkeypatch.setenv(mea.ENV_PYTHON, sys.executable)
    monkeypatch.setenv(mea.ENV_RUNNER, STUB)
    monkeypatch.setenv(mea.ENV_PROBE_IMPORT, "json")  # always importable
    assert mea.available() == (True, "ok")


# --------------------------------------------------------------------------- forecast_batch()


def test_forecast_batch_happy(monkeypatch):
    monkeypatch.setenv(mea.ENV_PYTHON, sys.executable)
    monkeypatch.setenv(mea.ENV_RUNNER, STUB)
    resp = mea.forecast_batch([{"id": "a|full", "series": [10.0, 20.0, 30.0], "horizon": 2}])
    assert resp["backend"] == "stub_runtime"
    assert resp["results"]["a|full"]["etc"] == 60.0  # last(30)*h(2)


def test_forecast_batch_not_configured():
    with pytest.raises(mea.ModelEngineUnavailable, match="not_configured"):
        mea.forecast_batch([{"id": "x", "series": [1.0], "horizon": 1}])


def test_forecast_batch_missing_runner(monkeypatch):
    monkeypatch.setenv(mea.ENV_PYTHON, sys.executable)
    monkeypatch.setenv(mea.ENV_RUNNER, "/no/such/runner.py")
    with pytest.raises(mea.ModelEngineUnavailable, match="interpreter_or_runner_missing"):
        mea.forecast_batch([{"id": "x", "series": [1.0], "horizon": 1}])


def test_forecast_batch_nonzero_exit(tmp_path, monkeypatch):
    runner = tmp_path / "fail_runner.py"
    runner.write_text("import sys; sys.stderr.write('boom'); sys.exit(1)\n", encoding="utf-8")
    monkeypatch.setenv(mea.ENV_PYTHON, sys.executable)
    monkeypatch.setenv(mea.ENV_RUNNER, str(runner))
    with pytest.raises(mea.ModelEngineUnavailable, match="runtime_exit_1"):
        mea.forecast_batch([{"id": "x", "series": [1.0], "horizon": 1}])


def test_forecast_batch_bad_json(tmp_path, monkeypatch):
    runner = tmp_path / "garbage_runner.py"
    runner.write_text("import sys; sys.stdout.write('not json {{{')\n", encoding="utf-8")
    monkeypatch.setenv(mea.ENV_PYTHON, sys.executable)
    monkeypatch.setenv(mea.ENV_RUNNER, str(runner))
    with pytest.raises(mea.ModelEngineUnavailable, match="bad_response"):
        mea.forecast_batch([{"id": "x", "series": [1.0], "horizon": 1}])


# --------------------------------------------------------------------------- runtime-backed artifacts


@pytest.mark.skipif(not _HAS_DATA, reason="local forecast data root not present")
def test_generate_uses_runtime_backend_when_available(tmp_path, monkeypatch):
    monkeypatch.setenv(mea.ENV_PYTHON, sys.executable)
    monkeypatch.setenv(mea.ENV_RUNNER, STUB)
    monkeypatch.setenv(mea.ENV_PROBE_IMPORT, "json")  # make available() true via the stub
    res = gen.generate(
        "tropical",
        CFG,
        data_root=DATA_ROOT,
        frozen_stamp="20260101_000000",
        out_root=tmp_path,
        with_llm=False,
    )
    out = Path(res["output_package"])
    bt = read_json(out / "audit" / "statsforecast_shadow_backtest.json")
    assert bt["backend"] == "stub_runtime"  # routed through the subprocess boundary
    comp = list(read_jsonl(out / "statsforecast_shadow_comparison.jsonl"))
    assert comp and all(r["backend"] == "stub_runtime" for r in comp)
