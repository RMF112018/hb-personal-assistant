"""End-to-end cost-frequency generation: gates, determinism, 127 coverage, staffing override, no mutation.

Skips when the local data root / required packages (context + accepted intelligence) are absent.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_cost_frequency import generate_forecast_cost_frequency_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)

STAMP = "20260101_000000"


def _generate(out_root):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=out_root,
                       with_llm=False)
    return Path(res["output_package"]), res


def test_validation_passes_and_no_mutation(tmp_path):
    out, res = _generate(tmp_path)
    rep = read_json(out / "validation_report.json")
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]
    assert res["source_hashes_unchanged"] is True
    assert res["determinism_passed"] is True
    for gate in ("all_127_canonical_covered_or_skipped", "staffing_codes_effective_weekly",
                 "weekday_calendar_for_every_forecast_month", "no_partial_month_as_complete_rate_basis",
                 "cadence_is_timing_only_no_final_cost_change", "source_hashes_unchanged",
                 "determinism_passed", "no_live_external_calls_localhost_llm_only"):
        assert rep["checks"][gate] is True, gate


def test_all_staffing_codes_effective_weekly(tmp_path):
    out, _ = _generate(tmp_path)
    freq = list(read_jsonl(out / "cost_frequency_by_budget_code.jsonl"))
    staffing = [r for r in freq if r["is_internal_staffing_code"]]
    assert len(staffing) == 23
    assert all(r["effective_frequency_class"] == "weekly_internal_staffing" for r in staffing)
    assert all(r["configured_frequency_override"] == "weekly_internal_staffing" for r in staffing)


def test_weekday_calendar_for_every_forecast_month(tmp_path):
    out, _ = _generate(tmp_path)
    window = read_json(out / "input_inventory.json")["forecast_window"]
    cal = list(read_jsonl(out / "weekday_calendar_by_forecast_month.jsonl"))
    assert [r["forecast_month"] for r in cal] == window["months"]
    assert all(isinstance(r["weekday_count"], int) and r["weekday_count"] > 0 for r in cal)


def test_package_contract_present_for_comprehensive(tmp_path):
    out, _ = _generate(tmp_path)
    summary = read_json(out / "project_cost_frequency_summary.json")
    contract = summary["package_contract"]
    assert contract["contract_version"] == "1.0.0"
    assert contract["consumable_by"] == "forecast_comprehensive"
    assert "frequency_adjusted_monthly_phasing_by_budget_code.jsonl" in contract["primary_artifacts"]


def test_determinism_byte_identical_quant_core(tmp_path):
    a, _ = _generate(tmp_path / "a")
    b, _ = _generate(tmp_path / "b")
    skip = {"manifest.json", "validation_report.json", "input_inventory.json"}
    env_audit = {"db_inventory.json", "source_files_used.json", "source_hashes_before_after.json"}
    for rel in sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file()):
        if (rel.parts and rel.parts[0] == "llm") or rel.name in skip or rel.name in env_audit:
            continue
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
