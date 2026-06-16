"""forecast_model_controls: monthly-integration e2e against the live Tropical data root.

Skips when the local data root / required predecessor packages are absent.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_monthly import generate_monthly_forecast_package as mgen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
STAMP = "20260102_000000"
ANCHOR_FIX = str(SUBPROJECT_ROOT / "tests" / "fixtures" / "forecast_model_controls" / "tropical"
                 / "code_forecast_model_controls.accepted_projected_cost.fixture.jsonl")
CONTROLLED_KEY = "1000.15-08-250.SUB"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))),
    reason="local forecast data root / required packages not present")


def _monthly_rows(pkg):
    return list(read_jsonl(Path(pkg) / "monthly_forecast_by_budget_code.jsonl"))


def test_monthly_applies_model_control_and_reconciles(tmp_path):
    res = mgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path,
                        control_file=ANCHOR_FIX)
    assert res["validation_passed"] is True
    rows = [r for r in _monthly_rows(res["output_package"]) if r["budget_code_key"] == CONTROLLED_KEY]
    assert rows and all(r["operator_model_controlled"] for r in rows)
    actual = Decimal(rows[0]["operator_controlled_final_cost"]) - sum(
        Decimal(r["recommended_month_cost"]) for r in rows)
    final = Decimal(rows[0]["recommended_final_cost"])
    rsum = sum(Decimal(r["recommended_month_cost"]) for r in rows)
    assert final == Decimal(rows[0]["operator_controlled_final_cost"])
    assert actual + rsum == final  # monthly reconciles to the controlled final
    # audit records the applied control
    audit = read_json(Path(res["output_package"]) / "audit" / "forecast_model_controls_applied.json")
    assert audit["model_controls_active"] is True
    assert audit["control_file_is_override"] is True
    assert any(a["budget_code_key"] == CONTROLLED_KEY for a in audit["applied_model_controls"])


def test_dormant_downstream_equivalence(tmp_path):
    """Dormant committed config must not change monthly numbers vs an empty control file."""
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    a = mgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path / "a",
                      control_file=str(empty))           # no controls at all
    b = mgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path / "b")  # dormant committed
    assert a["validation_passed"] and b["validation_passed"]
    ra = {(r["budget_code_key"], r["forecast_month"]): r for r in _monthly_rows(a["output_package"])}
    rb = {(r["budget_code_key"], r["forecast_month"]): r for r in _monthly_rows(b["output_package"])}
    assert ra.keys() == rb.keys()
    numeric = ("recommended_month_cost", "worst_credible_month_cost", "recommended_final_cost",
               "worst_credible_final_cost")
    for k in ra:
        for f in numeric:
            assert ra[k][f] == rb[k][f], (k, f)
    # no code is operator-controlled under the dormant committed config
    assert not any(r["operator_model_controlled"] for r in rb.values())
