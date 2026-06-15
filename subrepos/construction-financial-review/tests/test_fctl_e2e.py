"""forecast_controls end-to-end: determinism, validation gates, roofing stop, monthly application.

Skips when the local data root / required packages are absent.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.hashing import sha256_file
from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_controls import generate_forecast_controls_package as gen
from construction_financial_review.forecast_monthly import generate_monthly_forecast_package as mgen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
ROOFING = "1000.15-07-590.SUB"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)
STAMP = "20260101_000000"


def test_controls_package_valid_deterministic_and_roofing_applied(tmp_path):
    a = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                          out_root=tmp_path / "a")["output_package"])
    b = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                          out_root=tmp_path / "b")["output_package"])
    rep = read_json(a / "validation_report.json")
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]

    data_files = ["forecast_controls_by_budget_code.jsonl",
                  "forecast_controls_application_by_budget_code.jsonl",
                  "forecast_controls_monthly_adjustments_by_budget_code.jsonl",
                  "project_forecast_controls_summary.json",
                  "audit/control_application_audit.json"]
    for f in data_files:
        assert sha256_file(a / f) == sha256_file(b / f), f

    summary = read_json(a / "project_forecast_controls_summary.json")
    assert ROOFING in summary["controlled_budget_codes"]
    assert summary["applied_control_count"] == 1
    assert summary["acceptance_counts"]["pending"] == 1


def test_roofing_pending_queued_and_accepted_applied(tmp_path):
    out = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                            out_root=tmp_path)["output_package"])
    queue = list(read_jsonl(out / "forecast_controls_review_queue.jsonl"))
    pend = [q for q in queue if q["control_id"] == "tropical-roofing-15-07-590-closeout-2026-06"]
    assert pend and pend[0]["disposition"] == "superseded_by_accepted_control"

    adj = [a for a in read_jsonl(out / "forecast_controls_monthly_adjustments_by_budget_code.jsonl")
           if a["budget_code_key"] == ROOFING]
    assert adj, "expected a roofing monthly adjustment row"
    a0 = adj[0]
    assert a0["stop_month"] == "2026-07"
    if a0["monthly_preview_available"]:
        for mc in a0["after_month_costs"]:
            if mc["forecast_month"] > "2026-07":
                assert mc["recommended_month_cost"] == "0.00"


def test_forecast_monthly_stops_roofing_after_july(tmp_path):
    if not list(DATA_ROOT.glob("forecast_monthly_package_tropical_*")) and \
       not list(DATA_ROOT.glob("project_schedule_json_package")):
        pytest.skip("monthly prerequisites absent")
    res = mgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    out = Path(res["output_package"])
    rows = [r for r in read_jsonl(out / "monthly_forecast_by_budget_code.jsonl")
            if r["budget_code_key"] == ROOFING]
    by = {r["forecast_month"]: r["recommended_month_cost"] for r in rows}
    for m in by:
        if m > "2026-07":
            assert by[m] == "0.00", f"{m} not zeroed: {by[m]}"
    assert any(r["monthly_forecast_basis"].startswith("operator_controlled_") for r in rows)
    assert res["validation_passed"] is True
