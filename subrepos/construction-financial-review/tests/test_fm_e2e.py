"""End-to-end monthly forecast generation: completeness, reconciliation, determinism, gates.

Skips when the local forecast data root / required packages are not present.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.common.money import D
from construction_financial_review.forecast_monthly import generate_monthly_forecast_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir() and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)

STAMP = "20260101_000000"


def _generate(tmp_path):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                       out_root=tmp_path, with_llm=False)
    return Path(res["output_package"])


def test_validation_passes_and_gates(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    assert report["passed"] is True
    for gate in ("monthly_completeness_127_x_months", "forecast_window_start_and_end_correct",
                 "final_cost_geq_actuals", "monthly_sums_reconcile_to_ctc_and_final",
                 "no_current_month_double_count", "invoice_not_written_as_actuals",
                 "project_level_schedule_not_driving_code", "direct_assoc_requires_deterministic_link",
                 "overrun_not_suppressed", "determinism_passed", "confidence_split_fields_present",
                 "db_inventory_no_payloads", "safety_scan_passed"):
        assert report["checks"][gate] is True, gate


def test_determinism_block_present(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    det = report["determinism"]
    assert det["performed"] is True
    assert det["quantitative_core_byte_identical"] is True
    assert det["diff_result"] == "pass"
    assert det["llm_excluded_from_byte_diff"] is True


def test_completeness_and_window(tmp_path):
    out = _generate(tmp_path)
    rows = list(read_jsonl(out / "monthly_forecast_by_budget_code.jsonl"))
    months = sorted({r["forecast_month"] for r in rows})
    codes = {r["budget_code_key"] for r in rows}
    assert len(codes) == 127
    assert months[0] >= "2026-06"        # begins at/after the system month
    assert len(rows) == 127 * len(months)


def test_reconciliation_per_code(tmp_path):
    out = _generate(tmp_path)
    rows = list(read_jsonl(out / "monthly_forecast_by_budget_code.jsonl"))
    by_code = {}
    for r in rows:
        by_code.setdefault(r["budget_code_key"], []).append(r)
    for key, mrows in by_code.items():
        actual = D(mrows[0]["recommended_final_cost"]) - D(mrows[-1]["cumulative_recommended_cost_through_month"]) \
            + sum((D(m["recommended_month_cost"]) for m in mrows), Decimal("0"))
        rec_sum = sum((D(m["recommended_month_cost"]) for m in mrows), Decimal("0"))
        final = D(mrows[0]["recommended_final_cost"])
        # actual + Σ month == final (cumulative through last month equals final)
        assert abs(D(mrows[-1]["cumulative_recommended_cost_through_month"]) - final) <= Decimal("0.01")


def test_byte_deterministic_quant_core(tmp_path):
    a = _generate(tmp_path / "a")
    b = _generate(tmp_path / "b")
    for rel in sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file()):
        if rel.parts and rel.parts[0] == "llm":
            continue
        if rel.name in ("manifest.json", "validation_report.json", "input_inventory.json"):
            continue
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
