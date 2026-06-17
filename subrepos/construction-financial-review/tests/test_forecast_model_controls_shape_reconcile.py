"""Regression: shape-only model controls reconcile to the comprehensive integrated CTC.

A shape-only control (value_constraint none, changes_deterministic_final False) dictates timing only.
The comprehensive integrated CTC is history-blended and differs from the control's model-derived dollars;
the monthly consumer must reallocate the integrated CTC across the operator's curve so the row reconciles.
"""
from __future__ import annotations

import csv
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_comprehensive import monthly_consumer


def _sc():
    return {"history_consumption_status": "consumed", "frequency_consumption_status": "missing",
            "schedule_consumption_status": "missing", "history_monthly_shape_weight": Decimal("0"),
            "frequency_monthly_weight": Decimal("0")}


def _entry(mc):
    return {"monthly_dist": {"monthly_distribution_weights": [{"month": "2026-06", "weight": "1"}]},
            "freq_phasing": {}, "hist_mon": None, "model_control": mc, "dormant": None}


def test_shape_only_control_reallocates_integrated_ctc_and_preserves_curve():
    # operator allocation sums to the MODEL ctc (1000), but integrated_ctc is history-blended (900).
    mc = {"control_id": "c", "changes_deterministic_final": False, "controlled_remaining": Decimal("1000.00"),
          "controlled_final_cost": Decimal("1500.00"), "value_constraint_policy": "none",
          "model_type": "front_loaded_s_curve",
          "monthly_allocation": OrderedDict([("2026-06", Decimal("600.00")), ("2026-07", Decimal("300.00")),
                                             ("2026-08", Decimal("100.00"))]),
          "active_months": ["2026-06", "2026-07", "2026-08"], "resolved_start_date": None,
          "resolved_end_date": None, "schedule_end_basis": "x"}
    integrated_ctc = Decimal("900.00")   # history-blended, != model ctc 1000
    row, months, audit = monthly_consumer.build("tropical", "K", _entry(mc), _sc(), integrated_ctc)
    vals = [Decimal(m["integrated_month_cost"]) for m in row["monthly_costs"]]
    assert sum(vals) == integrated_ctc and row["reconciles_to_integrated_ctc"] is True
    assert audit["reconciled"] is True
    assert vals[0] > vals[1] > vals[2]                  # front-loaded curve preserved
    assert row["operator_model_type"] == "front_loaded_s_curve"   # shape/window metadata preserved
    assert row["operator_model_controlled"] is True


def test_value_changing_control_still_reconciles_unchanged():
    # value-changing: integrated_ctc == controlled_remaining; same path reproduces the allocation.
    mc = {"control_id": "v", "changes_deterministic_final": True, "controlled_remaining": Decimal("500.00"),
          "controlled_final_cost": Decimal("900.00"), "value_constraint_policy": "explicit_remaining_value",
          "model_type": "existing_model",
          "monthly_allocation": OrderedDict([("2026-06", Decimal("200.00")), ("2026-07", Decimal("300.00"))]),
          "active_months": ["2026-06", "2026-07"], "resolved_start_date": None, "resolved_end_date": None,
          "schedule_end_basis": "x"}
    row, months, audit = monthly_consumer.build("tropical", "K", _entry(mc), _sc(), Decimal("500.00"))
    vals = [Decimal(m["integrated_month_cost"]) for m in row["monthly_costs"]]
    assert sum(vals) == Decimal("500.00") and row["reconciles_to_integrated_ctc"] is True
    assert vals == [Decimal("200.00"), Decimal("300.00")]   # distribution unchanged


# ---- live comprehensive e2e (against the operator's accepted model controls) ----

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

livegate = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_probability_package_tropical_*"))),
    reason="local forecast data root / required packages not present")


@livegate
def test_comprehensive_all_model_controlled_rows_reconcile(tmp_path):
    from construction_financial_review.forecast_comprehensive import generate_comprehensive_forecast_package as cgen
    res = cgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp="20260105_000000", out_root=tmp_path)
    assert res["validation_passed"] is True
    pkg = Path(res["output_package"])

    mrows = list(read_jsonl(pkg / "integrated_monthly_forecast_by_budget_code.jsonl"))
    controlled = [r for r in mrows if r.get("operator_model_controlled")]
    assert all(r["reconciles_to_integrated_ctc"] for r in controlled)   # 51 formerly-failing rows reconcile
    # shape-only controlled rows preserve shape/window metadata
    for r in controlled:
        assert r.get("operator_model_type") is not None
        assert "operator_forecast_end_date" in r or r.get("operator_schedule_end_basis") is not None

    aud = read_json(pkg / "audit" / "monthly_reconciliation_audit.json")
    assert aud["per_code_all_reconciled"] is True and aud["project_total_reconciled"] is True
    assert aud["project_monthly_total"] == aud["integrated_cost_to_complete_total"]

    # combined actuals+forecast CSV reconciles for controlled keys to the integrated final
    capf = read_json(pkg / "audit" / "actuals_plus_forecast_monthly_by_cost_code_audit.json")
    assert capf["all_controlled_targets_reconcile"] is True

    # integrated CTC stays history-blended for shape-only controls (final != accepted where history applied)
    finals = {r["budget_code_key"]: r for r in read_jsonl(pkg / "integrated_forecast_by_budget_code.jsonl")}
    shape_only = [r for r in controlled if r.get("operator_model_value_constraint_policy") == "none"]
    if shape_only:
        # at least one shape-only code carries a nonzero history weight (history-blended, not model-pinned)
        assert any(Decimal(finals[r["budget_code_key"]].get("history_final_cost_weight") or "0") > 0
                   for r in shape_only)
