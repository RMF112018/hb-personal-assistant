"""End-to-end generator coverage: discovery, safety scan, determinism, 127-row invariant.

Skips automatically when the local forecast data root is not present (e.g. CI without the
SynologyDrive mount), so the unit suite stays portable.
"""
import json
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.schedule_analysis import (
    generate_schedule_integrated_forecast as gen,
)
from construction_financial_review.schedule_analysis import schedule_io

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT / CFG.get("schedule_package", "project_schedule_json_package")).is_dir()
    or not list(DATA_ROOT.glob("forecast_analysis_package_tropical_crosswalk_v2_*")),
    reason="local forecast data root / schedule package not present",
)

STAMP = "20260101_000000"


def _generate(tmp_path: Path) -> Path:
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    return Path(res["output_package"])


def test_discovery_finds_required_packages():
    packages = schedule_io.discover_packages(DATA_ROOT, CFG)
    assert packages["schedule_package"] is not None
    assert packages["context_package"] is not None
    assert packages["analysis_v2_package"] is not None


def test_end_to_end_validation_and_safety(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    assert report["passed"] is True
    assert report["checks"]["safety_scan_passed"] is True
    assert read_json(out / "audit" / "safety_scan_report.json")["passed"] is True


def test_one_row_per_canonical_key(tmp_path):
    out = _generate(tmp_path)
    recs = list(read_jsonl(out / "forecast_recommendations_schedule_integrated.jsonl"))
    keys = [r["budget_code_key"] for r in recs]
    assert len(keys) == 127 == len(set(keys))


def test_no_schedule_only_numeric_increase(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    assert report["checks"]["schedule_did_not_create_numeric_increase"] is True


def test_deterministic_output(tmp_path):
    """Two frozen-stamp runs produce byte-identical data files (manifest hashes included)."""
    a = _generate(tmp_path / "a")
    b = _generate(tmp_path / "b")
    names = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    for rel in names:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
