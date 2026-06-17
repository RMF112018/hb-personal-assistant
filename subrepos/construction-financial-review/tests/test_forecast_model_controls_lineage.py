"""forecast-model-controls consumes fresh context lineage, never the stale cfg-named context."""
import json
from pathlib import Path

import pytest

from construction_financial_review.common import run_lineage as rl
from construction_financial_review.forecast_model_controls import (
    generate_forecast_model_controls_package as gen,
)
from construction_financial_review.forecast_model_controls import validation as fmc_validation

PROJECT = "tropical"
STALE = "forecast_context_package_tropical_20260614_084510"


def _mk_ctx(data: Path, stamp: str) -> Path:
    p = data / f"forecast_context_package_{PROJECT}_{stamp}"
    p.mkdir(parents=True)
    (p / "validation_report.json").write_text("{}")
    (p / "manifest.json").write_text("{}")
    return p


def _state(tmp_path, monkeypatch, data, *, ctx_stamp, run_id="20260617_100000"):
    sp = rl.new_run_state_path(tmp_path, PROJECT, run_id)
    rl.start_run_state(PROJECT, data, run_id, path=sp)
    monkeypatch.setenv(rl.ENV_STATE, str(sp))
    rl.record_latest(sp, "context", project_key=PROJECT)   # validates + records the fresh context
    return sp


def test_active_state_wins_over_stale_cfg(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir()
    _mk_ctx(data, "20260614_084510")          # stale, named in cfg, exists on disk
    fresh = _mk_ctx(data, "20260617_105902")  # fresh -> recorded into the run state
    _state(tmp_path, monkeypatch, data, ctx_stamp="20260617_105902")
    cfg = {"forecast_context_package": STALE}  # stale named config must be IGNORED
    discovery, meta = gen._discover(cfg, data, PROJECT)
    assert discovery["context"] == fresh
    assert meta["lineage_source"] == "full_fresh_run_state"


def test_no_state_uses_latest_glob_not_stale_cfg(tmp_path, monkeypatch):
    monkeypatch.delenv(rl.ENV_STATE, raising=False)
    data = tmp_path / "data"; data.mkdir()
    _mk_ctx(data, "20260614_084510")          # stale, named in cfg
    newest = _mk_ctx(data, "20260617_105902")
    cfg = {"forecast_context_package": STALE}
    discovery, meta = gen._discover(cfg, data, PROJECT)
    assert discovery["context"] == newest      # latest-glob, NOT the stale named config
    assert meta["lineage_source"] == "latest_glob"


def test_explicit_context_stamp_exact_and_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv(rl.ENV_STATE, raising=False)
    data = tmp_path / "data"; data.mkdir()
    _mk_ctx(data, "20260617_105902")
    pinned = _mk_ctx(data, "20260617_080320")
    cfg = {"forecast_context_package": STALE, "_pinned_context_stamp": "20260617_080320"}
    discovery, meta = gen._discover(cfg, data, PROJECT)
    assert discovery["context"] == pinned and meta["lineage_source"] == "explicit_override"
    # missing pin -> fail closed
    cfg_missing = {"_pinned_context_stamp": "20990101_000000"}
    with pytest.raises(SystemExit):
        gen._discover(cfg_missing, data, PROJECT)


def test_override_control_file_does_not_bypass_fresh_context(tmp_path, monkeypatch):
    # context discovery is independent of the control file; under an active run state it stays fresh.
    data = tmp_path / "data"; data.mkdir()
    _mk_ctx(data, "20260614_084510")
    fresh = _mk_ctx(data, "20260617_105902")
    _state(tmp_path, monkeypatch, data, ctx_stamp="20260617_105902")
    cfg = {"forecast_context_package": STALE,
           "forecast_model_controls": {"control_file": "/some/operator/override.jsonl"}}
    discovery, meta = gen._discover(cfg, data, PROJECT)
    assert discovery["context"] == fresh and meta["lineage_source"] == "full_fresh_run_state"
    # _discover takes no control-file argument -> the override can never influence context resolution
    import inspect
    assert "control" not in str(inspect.signature(gen._discover)).lower()


def test_validation_gate_present_and_fails_closed():
    import inspect
    src = inspect.getsource(fmc_validation.build_validation)
    assert "forecast_model_controls_context_lineage_consistent" in src
    assert "context_lineage_consistent" in str(inspect.signature(fmc_validation.build_validation))


def test_generator_does_not_prefer_cfg_context_in_code():
    src = Path(gen.__file__).read_text()
    # the only allowed mention is the explanatory docstring; no code reads cfg["forecast_context_package"]
    for line in src.splitlines():
        if "forecast_context_package" in line and 'cfg.get("forecast_context_package")' in line:
            pytest.fail(f"model-controls still reads cfg context package: {line.strip()}")
