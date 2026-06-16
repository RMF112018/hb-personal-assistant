"""forecast_dormancy: live intelligence-origin e2e against the Tropical data root (writes only to tmp).

Hard-coded gate (objective point 12) over the four observed CLOSED - DO NOT USE codes. Skips when the
data root / required packages are absent.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_intelligence import generate_forecast_intelligence_package as igen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
STAMP = "20260104_000000"
EXAMPLE_CODES = ["0000.03-01-025.MAT", "0000.03-01-413.LAB", "0000.03-01-413.LBN", "0000.03-01-413.MAT"]

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_analysis_package_tropical_crosswalk_v2_*"))),
    reason="local forecast data root / required packages not present")


def _run(tmp_path):
    res = igen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    return Path(res["output_package"]), res


def test_four_closed_codes_suppressed(tmp_path):
    pkg, res = _run(tmp_path)
    assert res["validation_passed"] is True
    recs = {r["budget_code_key"]: r for r in read_jsonl(pkg / "forecast_recommendations_by_budget_code.jsonl")}
    status = {r["budget_code_key"]: r for r in read_jsonl(pkg / "dormant_code_status_by_budget_code.jsonl")}
    for k in EXAMPLE_CODES:
        r, s = recs[k], status[k]
        assert s["dormant_status"] == "closed_do_not_use", k
        assert s["suppression_applied"] is True, k
        assert r["recommended_cost_to_complete"] == "0.00", k
        assert r["recommended_final_cost"] == r["actual_cost_all_source_to_date"], k
        assert "CLOSED - DO NOT USE" in s["suppression_reason"] and "no recent actual cost" in s["suppression_reason"], k


def test_dormancy_gates_and_audit_present(tmp_path):
    pkg, res = _run(tmp_path)
    vr = read_json(pkg / "validation_report.json")
    for gate in ("dormant_suppressed_ctc_zero", "dormant_suppressed_final_equals_actual",
                 "dormant_suppression_did_not_change_actuals", "dormant_suppressed_final_not_below_actuals",
                 "no_positive_forecast_for_closed_without_evidence"):
        assert vr["checks"][gate] is True, gate
    audit = read_json(pkg / "audit" / "dormant_code_suppression_audit.json")
    assert audit["enabled"] is True
    assert set(EXAMPLE_CODES) <= set(audit["suppressed_budget_codes"])
    assert audit["status_counts"].get("closed_do_not_use", 0) >= 4


def test_actuals_not_reduced_and_final_not_below_actuals(tmp_path):
    pkg, _ = _run(tmp_path)
    recs = {r["budget_code_key"]: r for r in read_jsonl(pkg / "forecast_recommendations_by_budget_code.jsonl")}
    for k in EXAMPLE_CODES:
        r = recs[k]
        assert Decimal(r["recommended_final_cost"]) >= Decimal(r["actual_cost_all_source_to_date"])
        assert Decimal(r["actual_cost_all_source_to_date"]) > Decimal("0")  # actuals preserved, not zeroed
