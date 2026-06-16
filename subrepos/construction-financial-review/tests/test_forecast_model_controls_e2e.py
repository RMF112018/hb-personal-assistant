"""forecast_model_controls: end-to-end standalone package against the live Tropical data root.

Skips when the local data root / required predecessor packages are absent.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_model_controls import generate_forecast_model_controls_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
STAMP = "20260101_000000"
ANCHOR_FIX = str(SUBPROJECT_ROOT / "tests" / "fixtures" / "forecast_model_controls" / "tropical"
                 / "code_forecast_model_controls.accepted_projected_cost.fixture.jsonl")

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))),
    reason="local forecast data root / required packages not present")


def _rows(pkg, name):
    return list(read_jsonl(Path(pkg) / name))


def test_dormant_committed_config_passes_zero_applied(tmp_path):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    assert res["validation_passed"] is True
    assert res["applied_control_count"] == 0
    assert res["determinism_passed"] and res["source_hashes_unchanged"]


def test_dormant_is_deterministic(tmp_path):
    a = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path / "a")
    b = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path / "b")
    import hashlib
    for f in gen.DATA_FILES + gen.AUDIT_DATA_FILES:
        ha = hashlib.sha256(Path(a["output_package"], f).read_bytes()).hexdigest()
        hb = hashlib.sha256(Path(b["output_package"], f).read_bytes()).hexdigest()
        assert ha == hb, f


def test_anchoring_fixture_reconciles(tmp_path):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path,
                       control_file=ANCHOR_FIX)
    assert res["validation_passed"] and res["applied_control_count"] == 1
    pkg = res["output_package"]
    rt = _rows(pkg, "model_control_resolved_targets_by_budget_code.jsonl")[0]
    key = rt["budget_code_key"]
    final = Decimal(rt["controlled_final_cost"])
    actual = Decimal(rt["actual_cost_to_date"])
    # equal_to_reference projected_cost -> final equals projected cost, >= actuals
    assert final >= actual
    pv = _rows(pkg, "model_control_monthly_preview_by_budget_code.jsonl")[0]
    alloc = sum(Decimal(m["recommended_month_cost"]) for m in pv["monthly_allocation"])
    assert alloc == Decimal(pv["controlled_remaining"])
    assert actual + alloc == final
    assert pv["reconciles_to_target"] is True
    pa = _rows(pkg, "model_control_probability_assessment_by_budget_code.jsonl")[0]
    assert pa["budget_code_key"] == key
    assert pa["probability_status"] == "accepted_probability_anchor"  # this key has a prior prob row


def test_override_never_reads_committed_config(tmp_path):
    """An override run must surface ONLY the fixture control — never the committed dormant examples."""
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path,
                       control_file=ANCHOR_FIX)
    rows = _rows(res["output_package"], "model_controls_by_budget_code.jsonl")
    assert len(rows) == 1
    assert rows[0]["control_id"] == "tropical-fixture-equal-projected-cost-15-08-250"
    inv = read_json(Path(res["output_package"]) / "input_inventory.json")
    assert inv["control_file_is_override"] is True
    assert "tests/fixtures" in inv["control_file"]
