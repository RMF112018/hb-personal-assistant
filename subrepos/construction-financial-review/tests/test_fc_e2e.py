"""End-to-end comprehensive generation: gates, determinism, coverage, consumption, reconciliation.

Skips when the local data root / required packages are absent.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_comprehensive import generate_comprehensive_forecast_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_monthly_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_probability_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)
STAMP = "20260101_000000"


def _generate(out_root):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=out_root)
    return Path(res["output_package"]), res


def test_validation_and_consumption(tmp_path):
    out, res = _generate(tmp_path)
    rep = read_json(out / "validation_report.json")
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]
    assert res["canonical_codes_covered"] == 127
    assert res["determinism_passed"] is True and res["source_hashes_unchanged"] is True
    for gate in ("canonical_budget_code_coverage", "no_invented_budget_code_keys",
                 "cost_entries_actuals_primary_truth", "no_history_as_actual", "no_pay_apps_as_actual",
                 "no_upper_cap_audit_passed", "actuals_floor_preserved", "monthly_reconciliation_passed",
                 "probability_determinism_passed", "history_outputs_consumed_or_explicitly_downgraded",
                 "frequency_outputs_consumed_or_explicitly_missing", "human_acceptance_fields_present",
                 "evidence_lineage_present", "no_external_calls"):
        assert rep["checks"][gate] is True, gate


def test_completeness_matrix_and_consumption_statuses(tmp_path):
    out, _ = _generate(tmp_path)
    mm = read_json(out / "audit" / "model_evidence_completeness_matrix.json")
    statuses = {p["package_type"]: p["consumption_status"] for p in mm["packages"]}
    for required in ("context", "intelligence", "monthly", "probability"):
        assert statuses[required] == "consumed"
    assert statuses["cost_frequency"] in ("consumed", "missing")
    fr = list(read_jsonl(out / "integrated_forecast_by_budget_code.jsonl"))[0]
    for f in ("history_consumption_status", "frequency_consumption_status", "monthly_consumption_status",
              "probability_consumption_status", "schedule_consumption_status", "pay_app_consumption_status"):
        assert f in fr


def test_monthly_reconciles_per_code_and_project(tmp_path):
    out, _ = _generate(tmp_path)
    audit = read_json(out / "audit" / "monthly_reconciliation_audit.json")
    assert audit["per_code_all_reconciled"] is True
    assert audit["project_total_reconciled"] is True


def test_probability_is_deterministic_transform_not_monte_carlo(tmp_path):
    out, _ = _generate(tmp_path)
    audit = read_json(out / "audit" / "probability_adjustment_audit.json")
    assert audit["probability_method"] == "accepted_distribution_deterministic_adjustment"
    assert audit["deterministic_no_monte_carlo"] is True
    assert audit["deterministic_seed"] is not None


def test_no_caps_and_floor_and_acceptance(tmp_path):
    out, _ = _generate(tmp_path)
    cap = read_json(out / "audit" / "no_upper_cap_audit.json")
    floor = read_json(out / "audit" / "actuals_floor_audit.json")
    assert cap["no_upper_cap_anywhere"] is True and floor["all_floors_respected"] is True
    recs = list(read_jsonl(out / "integrated_final_cost_recommendations.jsonl"))
    assert recs and all(r["acceptance_status"] == "pending" and r["upper_cap_applied"] is False for r in recs)


def test_determinism_byte_identical_quant_core(tmp_path):
    a, _ = _generate(tmp_path / "a")
    b, _ = _generate(tmp_path / "b")
    skip = {"manifest.json", "validation_report.json", "input_inventory.json"}
    env_audit = {"db_inventory.json", "source_files_used.json", "source_packages_used.json",
                 "source_hashes_before_after.json"}
    for rel in sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file()):
        if (rel.parts and rel.parts[0] == "llm") or rel.name in skip or rel.name in env_audit:
            continue
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
