"""forecast_cost_basis: comprehensive-integration e2e against the live Tropical data root.

Proves the BudgetDetails projected-cost basis corrects the canonical under-forecast 1000.15-01-426.MAT
to selected final 52,778.50 / CTC 25,000.00 (monthly sums to 25,000.00), while operator controls,
suppression, and the actuals floor are preserved. Skips when the data root / required packages are absent.
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
STAMP = "20260104_000000"
SURVEY = "1000.15-01-426.MAT"
MANUAL_MONTHLY = "1000.15-16-110.SUB"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_probability_package_tropical_*"))),
    reason="local forecast data root / required packages not present")


def _rows(pkg, name):
    return list(read_jsonl(Path(pkg) / name))


def test_survey_code_resolves_to_budgetdetails_projected_cost_basis(tmp_path):
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    assert res["validation_passed"] is True
    pkg = res["output_package"]

    audit = read_json(Path(pkg) / "audit" / "forecast_cost_basis_decision_audit.json")
    assert all(audit["validation_checks"].values()), \
        [k for k, v in audit["validation_checks"].items() if not v]
    row = next(r for r in audit["rows"] if r["budget_code_key"] == SURVEY)
    assert row["cost_basis_status"] == "budgetdetails_projected_cost_basis"
    assert Decimal(row["selected_final_cost"]) == Decimal("52778.50")
    assert Decimal(row["selected_cost_to_complete"]) == Decimal("25000.00")
    assert Decimal(row["monthly_total_after_basis"]) == Decimal("25000.00")
    assert Decimal(row["final_reconciliation_variance"]) == Decimal("0.00")
    assert row["projected_cost_formula_reconciles"] is True

    frow = next(r for r in _rows(pkg, "integrated_final_cost_recommendations.jsonl")
                if r["budget_code_key"] == SURVEY)
    assert Decimal(frow["integrated_recommended_final_cost"]) == Decimal("52778.50")
    assert Decimal(frow["integrated_cost_to_complete"]) == Decimal("25000.00")
    assert frow["upper_cap_applied"] is False

    mrow = next(r for r in _rows(pkg, "integrated_monthly_forecast_by_budget_code.jsonl")
                if r["budget_code_key"] == SURVEY)
    msum = sum(Decimal(m["integrated_month_cost"]) for m in mrow["monthly_costs"])
    assert msum == Decimal("25000.00")
    # actual + monthly == selected final
    actual = Decimal(next(r["actual_cost_to_date"] for r in _rows(
        pkg, "integrated_forecast_by_budget_code.jsonl") if r["budget_code_key"] == SURVEY))
    assert actual + msum == Decimal("52778.50")


def test_manual_monthly_and_floor_and_no_cap_preserved(tmp_path):
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    pkg = res["output_package"]
    audit = read_json(Path(pkg) / "audit" / "forecast_cost_basis_decision_audit.json")
    by_key = {r["budget_code_key"]: r for r in audit["rows"]}

    # manual_monthly stays operator-controlled, never budgetdetails basis
    if MANUAL_MONTHLY in by_key:
        assert by_key[MANUAL_MONTHLY]["cost_basis_status"] != "budgetdetails_projected_cost_basis"

    # actuals floor: no selected final below actual cost to date
    for r in audit["rows"]:
        assert Decimal(r["selected_final_cost"]) >= Decimal(r["actual_cost_to_date"]) - Decimal("0.01")

    # projected-cost basis disclosed, never a hidden cap
    cap_audit = read_json(Path(pkg) / "audit" / "no_upper_cap_audit.json")
    assert cap_audit["no_upper_cap_anywhere"] is True
    floor_audit = read_json(Path(pkg) / "audit" / "actuals_floor_audit.json")
    assert floor_audit["all_floors_respected"] is True
