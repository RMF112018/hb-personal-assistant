"""Shadow-invariance + artifact tests for the time-series estimator (e2e on the local data root).

Proves that ``timeseries_eac`` is computed and emitted, that it NEVER enters the central forecast
(absent from every reconciliation basis / contributions list), and that the shadow comparison +
holdout backtest artifacts are emitted. Skips when the local forecast data root is absent.
"""

from pathlib import Path

import pytest
from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_intelligence import (
    generate_forecast_intelligence_package as gen,
)

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (
        DATA_ROOT.is_dir()
        and list(DATA_ROOT.glob("forecast_analysis_package_tropical_crosswalk_v2_*"))
        and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
    ),
    reason="local forecast data root / required packages not present",
)

STAMP = "20260101_000000"


def _generate(tmp_path: Path) -> Path:
    res = gen.generate(
        "tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path, with_llm=False
    )
    return Path(res["output_package"])


def test_timeseries_is_emitted_but_never_weighted(tmp_path):
    out = _generate(tmp_path)
    rows = list(read_jsonl(out / "forecast_model_evidence_by_budget_code.jsonl"))
    assert rows
    saw_shadow = False
    for r in rows:
        methods = [e["method"] for e in r["estimates"]]
        if "timeseries_eac" in methods:
            saw_shadow = True
            ts = next(e for e in r["estimates"] if e["method"] == "timeseries_eac")
            assert ts["source"] == "shadow_timeseries"
        # The shadow estimator must never appear in the weighted central forecast.
        assert "timeseries_eac" not in (r.get("reconciliation_basis") or "")
        assert "timeseries_eac" not in [c["method"] for c in (r.get("contributions") or [])]
    assert saw_shadow, "timeseries_eac estimate should be emitted for at least one code"


def test_shadow_artifacts_emitted(tmp_path):
    out = _generate(tmp_path)
    comparison = list(read_jsonl(out / "statsforecast_shadow_comparison.jsonl"))
    assert comparison, "shadow comparison should have rows"
    for row in comparison:
        assert {
            "budget_code_key",
            "timeseries_eac",
            "recommended_final_cost",
            "delta_timeseries_minus_recommended",
            "backend",
        } <= set(row)

    bt = read_json(out / "audit" / "statsforecast_shadow_backtest.json")
    assert bt["backend"]
    assert bt["eligible_code_count"] >= 1
    assert "engine_median_abs_pct_error" in bt
    assert "naive_median_abs_pct_error" in bt
    assert "engine_better_or_equal_rate" in bt
    assert isinstance(bt["per_code"], list) and bt["per_code"]


def test_validation_still_passes_with_shadow(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    assert report["passed"] is True
    # The shadow estimate is uncapped+floored like any estimate, so the gate still holds.
    assert report["checks"]["every_estimate_geq_actuals"] is True
