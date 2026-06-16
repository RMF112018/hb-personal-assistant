"""End-to-end generation test (skips if the local forecast data root is absent)."""
from pathlib import Path

import pytest
from construction_financial_review.cli import load_project
from construction_financial_review.common.io import read_json
from construction_financial_review.forecast_improvement_audit import (
    generate_forecast_improvement_audit_package as gen,
)

CFG = load_project("tropical")
DATA_ROOT = Path(CFG["default_data_root"])
STAMP = "20260101_000000"

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir()
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))),
    reason="local forecast data root / required packages not present")


def _generate(out_root):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP, out_root=out_root)
    return Path(res["output_package"]), res


def test_validation_passes_and_no_mutation(tmp_path):
    out, res = _generate(tmp_path)
    rep = read_json(out / "validation_report.json")
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]
    assert res["source_hashes_unchanged"] is True
    assert res["determinism_passed"] is True
    assert res["safety_passed"] is True


def test_governance_gates_present(tmp_path):
    out, _ = _generate(tmp_path)
    checks = read_json(out / "validation_report.json")["checks"]
    for gate in ("no_reference_caps_for_non_fee_codes", "fee_projected_budget_cap_enforced",
                 "actuals_floor_preserved", "no_historical_forecast_as_actual",
                 "sqlite_opened_read_only", "data_gaps_not_silently_skipped"):
        assert checks[gate] is True, f"gate failed: {gate}"


def test_fee_cap_diagnostic_present(tmp_path):
    out, _ = _generate(tmp_path)
    from construction_financial_review.common.io import read_jsonl
    fee = list(read_jsonl(out / "fee_cap_diagnostics.jsonl"))
    assert fee, "expected at least one fee-cap row"
    r = fee[0]
    assert r["fee_cap_basis"] in ("projected_budget_value", "none")
    assert r["requires_human_acceptance"] is True


def test_determinism_byte_identical_quant_core(tmp_path):
    a, _ = _generate(tmp_path / "a")
    b, _ = _generate(tmp_path / "b")
    skip = {"manifest.json", "validation_report.json", "input_inventory.json"}
    env_audit = {"db_inventory.json", "source_files_used.json", "source_hashes_before_after.json"}
    for rel in sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file()):
        if rel.name in skip or rel.name in env_audit:
            continue
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"
