"""forecast_controls end-to-end: determinism, validation gates, roofing stop, monthly application.

Skips when the local data root / required packages are absent.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.hashing import sha256_file
from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_controls import generate_forecast_controls_package as gen
from construction_financial_review.forecast_monthly import generate_monthly_forecast_package as mgen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])
ROOFING = "1000.15-07-590.SUB"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)
STAMP = "20260101_000000"


# posture-changing control types (zero months or change dollars) — require human acceptance to apply
POSTURE_TYPES = {"closeout_stop_date", "forecast_stop_date", "inactive_after_date",
                 "remaining_cost_allowance", "accepted_final_cost_override", "monthly_distribution_override"}


def test_controls_package_valid_deterministic_and_floor_and_cap_audits(tmp_path):
    """Current operator-control contract: parses, validates, zero ambiguous mappings, floor + no-hidden-cap
    audits pass, deterministic quantitative core. (File-agnostic — no hardcoded seed counts.)"""
    a = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                          out_root=tmp_path / "a")["output_package"])
    b = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                          out_root=tmp_path / "b")["output_package"])

    # deterministic quantitative core (byte-identical across two frozen runs)
    for f in ("forecast_controls_by_budget_code.jsonl",
              "forecast_controls_application_by_budget_code.jsonl",
              "forecast_controls_monthly_adjustments_by_budget_code.jsonl",
              "project_forecast_controls_summary.json",
              "audit/control_application_audit.json"):
        assert sha256_file(a / f) == sha256_file(b / f), f

    rep = read_json(a / "validation_report.json")
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]
    checks = rep["checks"]
    assert checks["no_ambiguous_mapping"] is True
    assert checks["actuals_floor_preserved"] is True
    assert checks["no_hidden_cap_without_accepted_control"] is True

    # ambiguous mappings count is zero
    mapping_audit = read_json(a / "audit" / "control_mapping_audit.json")
    assert mapping_audit["by_mapping_status"].get("ambiguous_cost_code", 0) == 0
    assert mapping_audit["ambiguous"] == []

    # floor + no-hidden-cap audits pass
    assert read_json(a / "audit" / "actuals_floor_audit.json")["all_floors_respected"] is True
    assert read_json(a / "audit" / "no_hidden_cap_audit.json")["no_hidden_cap"] is True

    # Roofing is controlled and at least one control is applied (current state, not a hardcoded count)
    summary = read_json(a / "project_forecast_controls_summary.json")
    assert ROOFING in summary["controlled_budget_codes"]
    assert summary["applied_control_count"] >= 1


def test_application_invariants_and_roofing_stop(tmp_path):
    """Application-level invariants over the live operator-control file + the Roofing stop still holds."""
    out = Path(gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                            out_root=tmp_path)["output_package"])
    apps = list(read_jsonl(out / "forecast_controls_application_by_budget_code.jsonl"))
    queued_ids = {q["control_id"] for q in
                  read_jsonl(out / "forecast_controls_review_queue.jsonl")}

    for r in apps:
        # every applied control maps to a canonical budget code
        if r["applied"]:
            assert r["budget_code_key"], r
        # timing-only controls never create a hidden dollar override (dollars only when accepted)
        if r["dollar_applied"]:
            assert r["acceptance_status"] == "accepted", r
        # accepted, explicitly-mapped, posture-changing controls are applied unless explicitly superseded
        if (r["acceptance_status"] == "accepted" and r["mapping_status"] == "mapped_explicit"
                and r["control_type"] in POSTURE_TYPES):
            assert r["applied"] is True or r["disposition"] == "superseded_by_accepted_control", r
        # pending posture-changing controls, if any, are not applied and are queued for review
        if r["acceptance_status"] == "pending" and r["control_type"] in POSTURE_TYPES:
            assert r["applied"] is False, r
            assert r["control_id"] in queued_ids, r

    assert any(r["applied"] for r in apps), "expected at least one applied control"

    # Roofing still stops after July 2026; post-stop months remain 0.00
    adj = [a for a in read_jsonl(out / "forecast_controls_monthly_adjustments_by_budget_code.jsonl")
           if a["budget_code_key"] == ROOFING]
    assert adj, "expected a roofing monthly adjustment row"
    a0 = adj[0]
    assert a0["stop_month"] == "2026-07"
    if a0["monthly_preview_available"]:
        for mc in a0["after_month_costs"]:
            if mc["forecast_month"] > "2026-07":
                assert mc["recommended_month_cost"] == "0.00"


def test_forecast_monthly_stops_roofing_after_july(tmp_path):
    if not list(DATA_ROOT.glob("forecast_monthly_package_tropical_*")) and \
       not list(DATA_ROOT.glob("project_schedule_json_package")):
        pytest.skip("monthly prerequisites absent")
    res = mgen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=tmp_path)
    out = Path(res["output_package"])
    rows = [r for r in read_jsonl(out / "monthly_forecast_by_budget_code.jsonl")
            if r["budget_code_key"] == ROOFING]
    by = {r["forecast_month"]: r["recommended_month_cost"] for r in rows}
    for m in by:
        if m > "2026-07":
            assert by[m] == "0.00", f"{m} not zeroed: {by[m]}"
    assert any(r["monthly_forecast_basis"].startswith("operator_controlled_") for r in rows)
    assert res["validation_passed"] is True
