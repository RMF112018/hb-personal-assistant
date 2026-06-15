"""Monthly cadence integration e2e: source_shares carries frequency_weight; cadence proves timing-only.

Skips when the local data root / required packages are absent.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_monthly import generate_monthly_forecast_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
STAFFING = set(CFG["forecast_cost_frequency"]["weekly_internal_staffing_budget_code_keys"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)


def _generate(out_root):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp="20260101_000000",
                       out_root=out_root, forecast_start_month="2026-06")
    return Path(res["output_package"]), res


def test_source_shares_carry_frequency_weight(tmp_path):
    out, res = _generate(tmp_path)
    assert res["validation_passed"] is True
    assert res["determinism_passed"] is True
    conf = list(read_jsonl(out / "monthly_forecast_confidence_by_budget_code.jsonl"))
    assert conf and all("frequency_weight" in c["source_shares"] for c in conf)


def test_cadence_reconciliation_proof_holds(tmp_path):
    out, _ = _generate(tmp_path)
    proof = read_json(out / "audit" / "cadence_reconciliation_proof.json")
    assert proof["all_codes_reconcile_to_ctc_and_final"] is True
    assert proof["accepted_final_cost_unchanged_by_cadence"] is True
    assert proof["reconciliation_failures"] == []
    assert proof["final_cost_mismatches"] == []
    assert proof["codes_with_frequency_share"] > 0


def test_staffing_code_phases_by_weekday_cadence(tmp_path):
    out, _ = _generate(tmp_path)
    conf = {c["budget_code_key"]: c for c in
            read_jsonl(out / "monthly_forecast_confidence_by_budget_code.jsonl")}
    # at least one staffing code present in the model uses the frequency cadence as its dominant basis
    staffing_present = [k for k in STAFFING if k in conf]
    assert staffing_present
    assert any(conf[k]["monthly_forecast_basis"] == "frequency_cadence"
               and float(conf[k]["source_shares"]["frequency_weight"]) > 0 for k in staffing_present)


def test_months_reconcile_to_ctc_with_cadence(tmp_path):
    out, _ = _generate(tmp_path)
    dists = list(read_jsonl(out / "remaining_work_monthly_distribution_by_budget_code.jsonl"))
    assert all("RECONCILIATION FAILED" not in (d.get("validation_notes") or "") for d in dists)
