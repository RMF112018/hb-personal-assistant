"""forecast_staffing_basis: comprehensive-integration e2e against the live Tropical data root.

Proves the accepted operator staffing-plan basis raises mapped `.LAB` under-forecasts to the
operator-planned remaining (1000.10-01-318.LAB: CTC 23,145.65 -> 109,045.44), reconciles monthly to
the staffing CTC, preserves the actuals floor, and never lowers a model-supported forecast without
explicit per-code acceptance. Skips when the data root / required packages are absent.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_comprehensive import generate_comprehensive_forecast_package as cgen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
STAMP = "20260617_060000"

# expected staffing-plan CTC for the 8 mapped staffing codes (objective Sec. 9)
EXPECTED_STAFFING_CTC = {
    "1000.10-01-302.LAB": "2761.70", "1000.10-01-310.LAB": "9607.43",
    "1000.10-01-311.LAB": "79346.29", "1000.10-01-314.LAB": "206280.16",
    "1000.10-01-315.LAB": "111331.00", "1000.10-01-317.LAB": "85356.96",
    "1000.10-01-318.LAB": "109045.44", "1000.10-01-460.LAB": "14998.94",
}

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_staffing_plan_package_tropical_*"))),
    reason="local forecast data root / required packages not present")


def _rows(pkg, name):
    return list(read_jsonl(Path(pkg) / name))


def test_staffing_basis_raises_318_and_reconciles(tmp_path):
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    assert res["validation_passed"] is True
    pkg = res["output_package"]

    audit = read_json(Path(pkg) / "audit" / "forecast_staffing_basis_decision_audit.json")
    assert all(audit["validation_checks"].values()), \
        [k for k, v in audit["validation_checks"].items() if not v]
    by_key = {r["budget_code_key"]: r for r in audit["rows"]}

    row = by_key["1000.10-01-318.LAB"]
    assert row["staffing_basis_status"] == "operator_staffing_plan_basis"
    assert Decimal(row["selected_cost_to_complete"]) == Decimal("109045.44")
    assert Decimal(row["selected_final_cost"]) == Decimal("408425.76")
    assert Decimal(row["monthly_total_after_staffing_basis"]) == Decimal("109045.44")
    assert Decimal(row["final_reconciliation_variance"]) == Decimal("0.00")

    frow = next(r for r in _rows(pkg, "integrated_final_cost_recommendations.jsonl")
                if r["budget_code_key"] == "1000.10-01-318.LAB")
    assert Decimal(frow["integrated_cost_to_complete"]) == Decimal("109045.44")
    assert frow["upper_cap_applied"] is False

    mrow = next(r for r in _rows(pkg, "integrated_monthly_forecast_by_budget_code.jsonl")
                if r["budget_code_key"] == "1000.10-01-318.LAB")
    msum = sum(Decimal(m["integrated_month_cost"]) for m in mrow["monthly_costs"])
    assert msum == Decimal("109045.44")


def test_all_eight_staffing_codes_raise_or_preserve(tmp_path):
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    pkg = res["output_package"]
    audit = read_json(Path(pkg) / "audit" / "forecast_staffing_basis_decision_audit.json")
    by_key = {r["budget_code_key"]: r for r in audit["rows"]}

    for code, staffing_ctc in EXPECTED_STAFFING_CTC.items():
        r = by_key[code]
        assert Decimal(r["staffing_plan_implied_remaining_cost"]) == Decimal(staffing_ctc)
        model_ctc = Decimal(r["current_model_cost_to_complete"])
        if Decimal(staffing_ctc) > model_ctc:  # raise -> staffing basis applied
            assert r["staffing_basis_status"] == "operator_staffing_plan_basis"
            assert Decimal(r["selected_cost_to_complete"]) == Decimal(staffing_ctc)
        else:                                   # decrease -> model preserved (no explicit acceptance)
            assert r["staffing_basis_status"] == "staffing_below_model_preserved"
            assert Decimal(r["selected_cost_to_complete"]) == model_ctc
        # actuals floor never violated
        assert Decimal(r["selected_final_cost"]) >= Decimal(r["actual_cost_to_date"]) - Decimal("0.01")
        # .LBN/.MAT siblings never numerically applied
        assert r["is_lab"] is True


def test_lbn_mat_and_lineage_audit_present(tmp_path):
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    pkg = res["output_package"]
    audit = read_json(Path(pkg) / "audit" / "forecast_staffing_basis_decision_audit.json")
    for r in audit["rows"]:
        assert not str(r["budget_code_key"]).endswith((".LBN", ".MAT")) \
            or r["staffing_basis_status"] != "operator_staffing_plan_basis"
    lineage = read_json(Path(pkg) / "audit" / "forecast_run_lineage_audit.json")
    assert "full_run_lineage_consistent" in lineage
    assert lineage["comprehensive_context_stamp"]
