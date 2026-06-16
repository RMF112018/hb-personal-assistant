"""End-to-end history-informed generation: gates, determinism, source-no-mutation, watch codes.

Skips when the local data root / required packages (historical + context + intelligence) are absent.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_history_informed import generate_forecast_history_informed_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and (DATA_ROOT / "cash_flow_forecast_history_json_package").is_dir()
         and (DATA_ROOT / "gcgr_forecast_history_json_package").is_dir()
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
    for gate in ("no_historical_forecast_as_actual", "no_prior_forecast_hard_cap",
                 "actuals_floor_preserved", "source_hashes_unchanged", "determinism_passed",
                 "gcgr_proportionality_audit_present", "cost_entries_actuals_primary_truth",
                 "no_live_external_calls_localhost_llm_only"):
        assert rep["checks"][gate] is True, gate


def test_watch_codes_reported(tmp_path):
    out, _ = _generate(tmp_path)
    mapping_audit = read_json(out / "audit" / "history_mapping_audit.json")
    presence = {p["cost_code"]: p for p in mapping_audit["watch_code_presence"]}
    # 15-16-100 verified absent across all sources; 20-18-110 maps to OVH
    assert presence["15-16-100"]["absent_everywhere"] is True
    assert presence["20-18-110"]["present_in_canonical_budget_details"] is True
    warns = list(read_jsonl(out / "historical_forecast_data_quality_warnings.jsonl"))
    assert any(w["cost_code"] == "15-16-100" and w["warning_type"] == "code_absent_all_sources"
               for w in warns)


def test_gcgr_fee_taper_audit(tmp_path):
    out, _ = _generate(tmp_path)
    audit = read_json(out / "audit" / "gcgr_proportionality_audit.json")
    assert "20-18-110" in audit["fee_codes_examined"]
    fee = next(f for f in audit["per_fee"] if f["cost_code"] == "20-18-110")
    assert fee["historical_decline_observed"] is True
    assert fee["proportionality_status"] in (
        "confirmed", "tapering_consistent_not_confirmed", "unsupported", "insufficient_evidence")


def test_monthly_distribution_uses_real_source_shares(tmp_path):
    out, _ = _generate(tmp_path)
    dist = list(read_jsonl(out / "history_informed_monthly_distribution_by_budget_code.jsonl"))
    # every advisory distribution row declares its source basis explicitly
    assert dist and all("source_shares_available" in d and "distribution_source_basis" in d
                        for d in dist)
    if list(DATA_ROOT.glob("forecast_monthly_package_tropical_*")):
        # with the accepted monthly package present, real source shares must reach at least some rows
        assert any(d["source_shares_available"] is True
                   and d["distribution_source_basis"] == "accepted_monthly_source_shares"
                   for d in dist)


def test_reliability_actual_evidence_support_fields(tmp_path):
    out, _ = _generate(tmp_path)
    rel = list(read_jsonl(out / "historical_assumption_reliability_by_budget_code.jsonl"))
    assert rel
    for r in rel:
        assert "invoice_support_score" not in r          # misleading field is gone
        for f in ("cost_entry_activity_support_score", "subcontractor_invoice_support_score",
                  "actual_history_density_support_score", "actual_evidence_support_score"):
            assert f in r, f


def test_determinism_byte_identical_quant_core(tmp_path):
    a, _ = _generate(tmp_path / "a")
    b, _ = _generate(tmp_path / "b")
    skip = {"manifest.json", "validation_report.json", "input_inventory.json"}
    env_audit = {"db_inventory.json", "safety_scan_report.json",
                 "historical_source_files_used.json", "source_hashes_before_after.json"}
    for rel in sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file()):
        if rel.parts and rel.parts[0] == "llm":
            continue
        if rel.name in skip or rel.name in env_audit:
            continue
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
