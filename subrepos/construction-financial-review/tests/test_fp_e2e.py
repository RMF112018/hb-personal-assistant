"""End-to-end probabilistic validation generation: gates, determinism, floor, no-cap, byte-identity.

Skips when the local forecast data root / required accepted packages are not present.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_probability import generate_probabilistic_validation_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)

STAMP = "20260101_000000"
RUNS = 2000
SEED = 20260614


def _generate(out_root):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                       out_root=out_root, with_llm=False, runs=RUNS, seed=SEED)
    return Path(res["output_package"])


def test_validation_passes_and_gates(tmp_path):
    out = _generate(tmp_path)
    report = read_json(out / "validation_report.json")
    assert report["passed"] is True, report["checks"]
    for gate in ("per_code_completeness_127", "canonical_only_codes", "percentile_monotonicity",
                 "final_cost_floor_at_actuals", "no_upper_cap_uncapped_upside",
                 "no_upper_cap_audit_present", "no_code_upper_capped",
                 "no_cap_source_is_reference_value",
                 "revised_budget_probability_present_and_unit_interval",
                 "compatibility_alias_files_present_and_parseable",
                 "forecast_start_month_no_full_ctc_reallocation",
                 "p50_aligns_with_deterministic_recommended", "monthly_reconciles_to_simulated_ctc",
                 "probability_fields_in_unit_interval", "sensitivity_ranking_present",
                 "backtest_cohort_reported", "determinism_passed", "db_inventory_no_payloads",
                 "safety_scan_passed"):
        assert report["checks"][gate] is True, gate


def test_compatibility_alias_files_emitted_and_parse(tmp_path):
    out = _generate(tmp_path)
    # straight-copy aliases mirror their canonical source row-for-row
    assert (read_json(out / "simulation_results_project.json")
            == read_json(out / "probabilistic_project_summary.json"))
    assert (list(read_jsonl(out / "simulation_results_by_budget_code.jsonl"))
            == list(read_jsonl(out / "probabilistic_final_cost_by_budget_code.jsonl")))
    assert (list(read_jsonl(out / "simulation_results_by_month.jsonl"))
            == list(read_jsonl(out / "probabilistic_monthly_project_forecast.jsonl")))
    # register is a MATERIAL subset, each row carries its threshold basis
    register = list(read_jsonl(out / "probabilistic_overrun_risk_register.jsonl"))
    code_rows = list(read_jsonl(out / "probabilistic_final_cost_by_budget_code.jsonl"))
    assert len(register) <= len(code_rows)
    for r in register:
        assert r["materiality_threshold_basis"]
        assert Decimal(r["prob_exceeds_current_projected_cost"]) >= Decimal("0.20")
    # division + per-code sensitivity parse; owner-scope is always present + parseable
    assert list(read_jsonl(out / "budget_code_sensitivity.jsonl"))
    assert list(read_jsonl(out / "division_sensitivity.jsonl"))
    assert list(read_jsonl(out / "owner_scope_sensitivity.jsonl"))


def test_no_upper_cap_audit_present_and_uncapped(tmp_path):
    out = _generate(tmp_path)
    audit = read_json(out / "audit" / "no_upper_cap_audit.json")
    assert len(audit) == 127
    refs = {"erp", "revised_budget", "committed", "owner_sov", "procore_pay_app", "prior_output"}
    for a in audit:
        assert a["upper_cap_applied"] is False
        assert a["upper_cap_source"] is None
        assert a["reference_values_reported_only"] is True
        assert a["upper_cap_source"] not in refs
        assert a["validation_status"] in {"uncapped_ok", "near_complete_point_mass"}


def test_project_revised_budget_probability_in_package(tmp_path):
    out = _generate(tmp_path)
    s = read_json(out / "probabilistic_project_summary.json")
    assert Decimal("0") <= Decimal(s["probability_project_exceeds_revised_budget_total"]) <= Decimal("1")
    for q in (80, 90, 95):
        assert Decimal(s[f"p{q}_overrun_vs_revised_budget_total"]) >= Decimal("0")
    wr = s["window_reconciliation"]
    assert wr["forecast_start_override_active"] is False
    assert Decimal(wr["deterministic_prior_forecast_before_probability_window"]) == Decimal("0.00")


def test_determinism_block_records_frozen_stamp(tmp_path):
    out = _generate(tmp_path)
    det = read_json(out / "validation_report.json")["determinism"]
    assert det["performed"] is True
    assert det["quantitative_core_byte_identical"] is True
    assert det["diff_result"] == "pass"
    assert det["frozen_stamp"] == STAMP
    assert det["seed"] == SEED


def test_floor_and_uncapped(tmp_path):
    out = _generate(tmp_path)
    rows = list(read_jsonl(out / "probabilistic_final_cost_by_budget_code.jsonl"))
    assert len(rows) == 127
    # actuals floor: P10 >= actual for every code
    for r in rows:
        assert Decimal(r["simulated_p10"]) >= Decimal(r["actual_cost_to_date"])
    # uncapped upside: at least one code's P95 exceeds its deterministic worst-credible
    assert any(Decimal(r["simulated_p95"]) > Decimal(r["deterministic_worst_credible_final_cost"])
               for r in rows if not r["near_complete"])


def test_recommended_is_central_and_percentiles_monotonic(tmp_path):
    out = _generate(tmp_path)
    s = read_json(out / "probabilistic_project_summary.json")
    rank = float(s["recommended_final_percentile_rank"])
    assert 20.0 <= rank <= 80.0
    sp = s["simulated_final_cost_percentiles"]
    vals = [Decimal(sp[k]) for k in ("p10", "p50", "p80", "p90", "p95")]
    assert vals == sorted(vals)


def test_pit_coverage_backtest_present(tmp_path):
    out = _generate(tmp_path)
    bt = read_json(out / "probabilistic_backtest_results.json")
    assert bt["primary"] == "pit_coverage_calibration"
    assert "n_pit_points" in bt and "cohort_size" in bt
    assert bt["calibration_verdict"] in {
        "insufficient_cohort", "under_dispersed", "over_dispersed",
        "well_calibrated", "approximately_calibrated"}
    pit = bt["pit_coverage"]
    for field in ("coverage_p10_p90", "coverage_p05_p95", "pit_mean_target_0_5", "pit_deciles"):
        assert field in pit
    # with the real near-complete cohort we expect at least some scorable points
    assert bt["n_pit_points"] >= 1
    for p in pit["pit_points"]:
        assert Decimal("0") <= Decimal(p["pit"]) <= Decimal("1")
    assert bt["dispersion_adequacy_secondary"]["method"] == "dispersion_adequacy_vs_historical_mape"


def test_byte_deterministic_quant_core(tmp_path):
    a = _generate(tmp_path / "a")
    b = _generate(tmp_path / "b")
    skip = {"manifest.json", "validation_report.json", "input_inventory.json"}
    for rel in sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file()):
        if rel.parts and rel.parts[0] in ("llm", "audit"):
            continue
        if rel.name in skip:
            continue
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
