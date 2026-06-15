"""forecast_staffing_plan end-to-end: discovery/validation, determinism, applied LAB mapping, CLI.

Skips when the local data root / staffing package / required packages are absent.
"""
from pathlib import Path

import pytest

from construction_financial_review.cli import build_parser
from construction_financial_review.common.hashing import sha256_file
from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_staffing_plan import generate_forecast_staffing_plan_package as gen
from construction_financial_review.forecast_staffing_plan import package_discovery

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
STAMP = "20260101_000000"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("staffing_json_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))),
    reason="local data root / staffing + required packages not present",
)


def test_cli_registers_forecast_staffing_plan():
    args = build_parser().parse_args(["forecast-staffing-plan", "--project", "tropical",
                                      "--frozen-stamp", STAMP, "--out-root", "/tmp/x"])
    assert args.command == "forecast-staffing-plan"
    assert args.project == "tropical"


def test_source_package_discovery_validates():
    disc = package_discovery.discover(CFG, DATA_ROOT)
    assert disc["present"] and disc["structurally_valid"], package_discovery.gate_reasons(disc)
    assert disc["source_validation_passed"] and disc["source_hashes_verified"]
    assert disc["monthly_totals_reconcile"]


def test_package_valid_deterministic_and_lab_only(tmp_path):
    a = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                          out_root=tmp_path / "a")["output_package"])
    b = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                          out_root=tmp_path / "b")["output_package"])
    rep = read_json(a / "validation_report.json")
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]

    for f in ("staffing_plan_monthly_by_budget_code.jsonl", "staffing_plan_summary_by_budget_code.jsonl",
              "staffing_plan_mapping_by_cost_code.jsonl", "project_staffing_plan_summary.json",
              "audit/monthly_reconciliation_audit.json"):
        assert sha256_file(a / f) == sha256_file(b / f), f

    # every applied numeric target is a .LAB key (LAB-only rule)
    for m in read_jsonl(a / "staffing_plan_mapping_by_cost_code.jsonl"):
        if m["applied_numeric"]:
            assert m["numeric_target_budget_code_key"].endswith(".LAB")


def test_bridge_emits_both_vectors_and_floor(tmp_path):
    out = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                            out_root=tmp_path)["output_package"])
    summ = list(read_jsonl(out / "staffing_plan_summary_by_budget_code.jsonl"))
    assert summ, "expected applied staffing-plan summary rows"
    for r in summ:
        # the bridge always carries both monthly vectors + the deltas + floor preservation
        assert r["staffing_plan_implied_monthly_forecast"] is not None
        assert "delta_vs_current_accepted_ctc" in r
        assert "delta_vs_current_accepted_final_cost" in r
        assert r["actuals_floor_preserved"] is True
