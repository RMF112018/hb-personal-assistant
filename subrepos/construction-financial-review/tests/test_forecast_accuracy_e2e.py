"""End-to-end forecast-accuracy generation: floors, 127 rows, safety, determinism (mock).

Skips when the local forecast data root / required packages are not present.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_accuracy import generate_forecast_accuracy_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir() and list(DATA_ROOT.glob("forecast_analysis_package_tropical_crosswalk_v2_*"))
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)

STAMP = "20260101_000000"


def _generate(tmp_path: Path) -> Path:
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                       out_root=tmp_path, with_llm=False)
    return Path(res["output_package"])


def test_validation_and_safety_pass(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    assert report["passed"] is True
    assert report["checks"]["model_recommended_floored_to_actuals"] is True
    assert report["checks"]["every_estimate_floored_to_actuals"] is True
    assert report["checks"]["safety_scan_passed"] is True


def test_one_row_per_canonical_key(tmp_path):
    out = _generate(tmp_path)
    for fname in ("forecast_accuracy_recommendations.jsonl", "forecast_reconciliation_by_budget_code.jsonl",
                  "forecast_confidence_by_budget_code.jsonl", "forecast_adequacy_by_budget_code.jsonl",
                  "signal_bundle_by_budget_code.jsonl", "eac_estimates_by_budget_code.jsonl"):
        rows = list(read_jsonl(out / fname))
        keys = [r["budget_code_key"] for r in rows]
        assert len(keys) == 127 == len(set(keys)), fname


def test_backtest_present(tmp_path):
    out = _generate(tmp_path)
    bt = read_json(out / "backtest" / "backtest_accuracy_by_method.json")
    assert bt["cohort_size"] >= 1
    assert bt["calibration_weights"]


def test_deterministic_mock_output(tmp_path):
    a = _generate(tmp_path / "a")
    b = _generate(tmp_path / "b")
    names = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    for rel in names:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
