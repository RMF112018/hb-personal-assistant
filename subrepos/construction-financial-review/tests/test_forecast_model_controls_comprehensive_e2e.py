"""forecast_model_controls: comprehensive-integration e2e against the live Tropical data root.

Proves the section-21 reconciliation: integrated final, combined CSV, and probability anchor all equal
the controlled target for a controlled code. Skips when the data root / required packages are absent.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_comprehensive import generate_comprehensive_forecast_package as cgen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
STAMP = "20260103_000000"
ANCHOR_FIX = str(SUBPROJECT_ROOT / "tests" / "fixtures" / "forecast_model_controls" / "tropical"
                 / "code_forecast_model_controls.accepted_projected_cost.fixture.jsonl")
KEY = "1000.15-08-250.SUB"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_probability_package_tropical_*"))),
    reason="local forecast data root / required packages not present")


def _rows(pkg, name):
    return list(read_jsonl(Path(pkg) / name))


def test_comprehensive_reconciles_controlled_target(tmp_path):
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path,
                        control_file=ANCHOR_FIX)
    assert res["validation_passed"] is True
    pkg = res["output_package"]

    target = next(Decimal(r["integrated_recommended_final_cost"])
                  for r in _rows(pkg, "integrated_final_cost_recommendations.jsonl")
                  if r["budget_code_key"] == KEY)

    # monthly reconciles to the controlled final
    mrow = next(r for r in _rows(pkg, "integrated_monthly_forecast_by_budget_code.jsonl")
                if r["budget_code_key"] == KEY)
    msum = sum(Decimal(m["integrated_month_cost"]) for m in mrow["monthly_costs"])
    assert mrow["operator_model_controlled"] is True
    assert Decimal(mrow["integrated_cost_to_complete"]) == msum

    # probability anchored to the controlled final
    prow = next(r for r in _rows(pkg, "integrated_probability_by_budget_code.jsonl")
                if r["budget_code_key"] == KEY)
    assert prow["operator_final_value_anchor_applied"] is True
    assert Decimal(prow["integrated_p50"]) == target

    # combined actuals+forecast CSV row sums to the controlled final
    with open(Path(pkg) / "actuals_plus_forecast_monthly_by_budget_code.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    row = next(r for r in rows if r["budget_code_key"] == KEY)
    month_cols = [c for c in row if len(c) == 7 and c[4] == "-"]
    assert sum(Decimal(row[c]) for c in month_cols if row[c] not in ("", None)) == target

    audit = read_json(Path(pkg) / "audit" / "actuals_plus_forecast_monthly_by_cost_code_audit.json")
    assert audit["all_controlled_targets_reconcile"] is True


def test_comprehensive_dormant_passes_no_controls(tmp_path):
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    assert res["validation_passed"] is True
    audit = read_json(Path(res["output_package"]) / "audit"
                      / "actuals_plus_forecast_monthly_by_cost_code_audit.json")
    assert audit["controlled_target_reconciliation"] == []
