"""Full-fresh-run lineage state for the analysis/crosswalk chain (common/run_lineage + generators)."""
import importlib
import json
from pathlib import Path

import pytest

from construction_financial_review.common import run_lineage as rl

PROJECT = "tropical"
SRC_DIR = Path(rl.__file__).resolve().parents[1]   # .../construction_financial_review


def _mkpkg(data: Path, name: str) -> Path:
    p = data / name
    p.mkdir(parents=True)
    (p / "validation_report.json").write_text("{}")
    (p / "manifest.json").write_text("{}")
    return p


def _state_with(tmp_path, monkeypatch, *, record=(), run_id="20260617_080000"):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    sp = rl.new_run_state_path(tmp_path, PROJECT, run_id)
    rl.start_run_state(PROJECT, data, run_id, path=sp)
    monkeypatch.setenv(rl.ENV_STATE, str(sp))
    for ptype, name in record:
        _mkpkg(data, name)
        rl.record_latest(sp, ptype, project_key=PROJECT)
    return data, sp


# ---- state lifecycle ----

def test_start_run_state_shape(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    sp = rl.new_run_state_path(tmp_path, PROJECT, "20260617_080000")
    rl.start_run_state(PROJECT, data, "20260617_080000", path=sp)
    st = json.load(open(sp))
    assert st["project_key"] == PROJECT and st["run_id"] == "20260617_080000"
    assert st["data_root"] == str(data) and st["packages"] == {}
    assert sp.name == "full_fresh_tropical_20260617_080000.json"


def test_record_latest_validates_and_records(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch, run_id="20260617_080000")
    _mkpkg(data, "forecast_analysis_package_tropical_20260617_080100")
    rec = rl.record_latest(sp, "analysis", project_key=PROJECT)
    assert rec["stamp"] == "20260617_080100"
    assert json.load(open(sp))["packages"]["analysis"]["stamp"] == "20260617_080100"


def test_record_rejects_prerun_stale_package(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch, run_id="20260617_080000")
    _mkpkg(data, "forecast_analysis_package_tropical_20260614_095847")   # predates run_id
    with pytest.raises(SystemExit):
        rl.record_latest(sp, "analysis", project_key=PROJECT)


def test_record_rejects_missing_validation_report(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch, run_id="20260617_080000")
    bad = data / "forecast_analysis_package_tropical_20260617_080100"; bad.mkdir()  # no validation_report
    with pytest.raises(SystemExit):
        rl.record_latest(sp, "analysis", project_key=PROJECT)


# ---- resolution ----

def test_resolve_from_active_state(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch,
                           record=[("analysis", "forecast_analysis_package_tropical_20260617_080100")])
    pkg, meta = rl.resolve_upstream("analysis", data_root=data, project_key=PROJECT)
    assert meta["lineage_source"] == "full_fresh_run_state"
    assert pkg.name.endswith("080100")


def test_active_state_missing_required_fails_closed(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch)   # nothing recorded
    with pytest.raises(SystemExit):
        rl.resolve_upstream("context", data_root=data, project_key=PROJECT)


def test_no_latest_glob_during_active_state(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch,
                           record=[("analysis", "forecast_analysis_package_tropical_20260617_080100")])
    # a NEWER non-recorded package on disk must be ignored (no latest-glob during active state)
    _mkpkg(data, "forecast_analysis_package_tropical_20260617_090000")
    pkg, meta = rl.resolve_upstream("analysis", data_root=data, project_key=PROJECT)
    assert pkg.name.endswith("080100") and meta["lineage_source"] == "full_fresh_run_state"


def test_explicit_override_resolves_exact(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch)
    _mkpkg(data, "forecast_context_package_tropical_20260617_081111")
    pkg, meta = rl.resolve_upstream("context", data_root=data, project_key=PROJECT,
                                    override_stamp="20260617_081111")
    assert meta["lineage_source"] == "explicit_override" and pkg.name.endswith("081111")


def test_override_missing_fails_closed(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch)
    with pytest.raises(SystemExit):
        rl.resolve_upstream("context", data_root=data, project_key=PROJECT, override_stamp="20990101_000000")


def test_backwards_compatible_latest_glob_without_state(tmp_path, monkeypatch):
    monkeypatch.delenv(rl.ENV_STATE, raising=False)
    data = tmp_path / "data"; data.mkdir()
    _mkpkg(data, "forecast_analysis_package_tropical_20260101_000000")
    newest = _mkpkg(data, "forecast_analysis_package_tropical_20260617_080100")
    # crosswalk_v2 shares the analysis prefix but must be excluded from `analysis`
    _mkpkg(data, "forecast_analysis_package_tropical_crosswalk_v2_20260617_090000")
    pkg, meta = rl.resolve_upstream("analysis", data_root=data, project_key=PROJECT)
    assert pkg == newest and meta["lineage_source"] == "latest_glob"


# ---- hard stale-lineage assert (refinement #6) ----

def test_no_stale_hardcoded_package_paths_in_generators():
    forbidden = (
        "forecast_context_package_tropical_20260614_084510",
        "forecast_analysis_package_tropical_20260614_095847",
        "mapping_discrepancy_workpaper_tropical_20260614_105720",
    )
    files = [
        SRC_DIR / "analysis" / "generate_forecast_analysis_package.py",
        SRC_DIR / "mapping" / "generate_mapping_discrepancy_workpaper.py",
        SRC_DIR / "analysis" / "generate_forecast_analysis_crosswalk_v2.py",
    ]
    for f in files:
        text = f.read_text()
        for bad in forbidden:
            assert bad not in text, f"stale package path {bad} still present in {f.name}"
    # the only allowed 20260614 reference in CODE is the authoritative owner-SOV crosswalk (comments ok)
    xw = (SRC_DIR / "analysis" / "generate_forecast_analysis_crosswalk_v2.py").read_text()
    for line in xw.splitlines():
        if "20260614" in line and not line.strip().startswith("#"):
            assert "owner_sov_scope_crosswalk" in line or "XW_AUTHORITATIVE_NAME" in line, \
                f"unexpected 20260614 ref: {line.strip()}"


# ---- runtime (not import) resolution in the generators ----

@pytest.mark.parametrize("modname,attr", [
    ("construction_financial_review.analysis.generate_forecast_analysis_package", "INPUT"),
    ("construction_financial_review.mapping.generate_mapping_discrepancy_workpaper", "CTX"),
    ("construction_financial_review.analysis.generate_forecast_analysis_crosswalk_v2", "CTX"),
])
def test_generators_do_not_resolve_at_import(modname, attr):
    mod = importlib.import_module(modname)
    assert getattr(mod, attr) is None and mod.ROOT is None   # no FS read / resolution at import


def test_generator_resolve_inputs_consumes_state(tmp_path, monkeypatch):
    data, sp = _state_with(tmp_path, monkeypatch, run_id="20260617_080000", record=[
        ("context", "forecast_context_package_tropical_20260617_080010"),
        ("analysis", "forecast_analysis_package_tropical_20260617_080020"),
        ("mapping_workpaper", "mapping_discrepancy_workpaper_tropical_20260617_080030"),
    ])
    mod = importlib.import_module(
        "construction_financial_review.analysis.generate_forecast_analysis_crosswalk_v2")
    mod.resolve_inputs()
    assert mod.CTX.name.endswith("080010") and mod.ANL.name.endswith("080020")
    assert mod.WP.name.endswith("080030")
    assert mod.CONTEXT_LINEAGE["lineage_source"] == "full_fresh_run_state"
    # authoritative owner-SOV crosswalk resolves by its fixed governance name under the run data root
    assert mod.XW_DIR.name == "owner_sov_scope_crosswalk_tropical_authoritative_20260614_final"


def test_generator_resolve_inputs_fails_closed_on_missing_upstream(tmp_path, monkeypatch):
    # state has context only; the workpaper generator requires analysis -> fail closed
    _state_with(tmp_path, monkeypatch, run_id="20260617_080000", record=[
        ("context", "forecast_context_package_tropical_20260617_080010")])
    mod = importlib.import_module(
        "construction_financial_review.mapping.generate_mapping_discrepancy_workpaper")
    with pytest.raises(SystemExit):
        mod.resolve_inputs()
