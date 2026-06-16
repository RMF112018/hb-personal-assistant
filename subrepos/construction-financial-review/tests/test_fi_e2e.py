"""End-to-end forecast-intelligence generation: 127 rows, floors, uncapped, safety, determinism.

Skips when the local forecast data root / required packages are not present.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.common.money import D
from construction_financial_review.forecast_intelligence import generate_forecast_intelligence_package as gen

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


def test_validation_passes_and_gates(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    assert report["passed"] is True
    for gate in ("final_cost_geq_actuals", "every_estimate_geq_actuals", "forecast_is_uncapped",
                 "overrun_not_suppressed", "direct_assoc_requires_deterministic_link",
                 "no_payapp_overwrite_of_actuals", "db_inventory_no_payloads", "safety_scan_passed"):
        assert report["checks"][gate] is True, gate


def test_one_row_per_canonical_key(tmp_path):
    out = _generate(tmp_path)
    for fname in ("forecast_recommendations_by_budget_code.jsonl",
                  "forecast_accuracy_next_by_budget_code.jsonl",
                  "forecast_model_evidence_by_budget_code.jsonl",
                  "schedule_forecast_evidence_by_budget_code.jsonl",
                  "trend_evidence_by_budget_code.jsonl",
                  "remaining_work_evidence_by_budget_code.jsonl",
                  "forecast_confidence_by_budget_code.jsonl",
                  "forecast_change_explanation.jsonl"):
        keys = [r["budget_code_key"] for r in read_jsonl(out / fname)]
        assert len(keys) == 127 == len(set(keys)), fname


def test_final_cost_floored_to_actuals(tmp_path):
    out = _generate(tmp_path)
    for r in read_jsonl(out / "forecast_recommendations_by_budget_code.jsonl"):
        assert D(r["recommended_final_cost"]) >= D(r["actual_cost_all_source_to_date"])
        assert D(r["worst_credible_final_cost"]) >= D(r["recommended_final_cost"])


def test_forecast_can_exceed_erp(tmp_path):
    out = _generate(tmp_path)
    rows = list(read_jsonl(out / "forecast_recommendations_by_budget_code.jsonl"))
    assert any(r["overrun_projected"] for r in rows)               # overruns surfaced
    assert any(r["overrun_vs_revised_budget"] for r in rows)       # exceeds budget where supported


def test_db_inventory_no_payloads(tmp_path):
    out = _generate(tmp_path)
    inv = read_json(out / "audit" / "db_inventory.json")
    if inv.get("db_present"):
        allowed = {"table", "present", "column_names", "row_count", "project_row_count"}
        for t in inv["tables"]:
            assert set(t.keys()) <= allowed


def test_deterministic_mock_output(tmp_path):
    a = _generate(tmp_path / "a")
    b = _generate(tmp_path / "b")
    for rel in sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file()):
        if rel.parts and rel.parts[0] == "llm":
            continue
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
