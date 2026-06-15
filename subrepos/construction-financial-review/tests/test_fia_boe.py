"""Priority 2 Basis-of-Estimate required-section + coverage tests."""
from construction_financial_review.forecast_improvement_audit import boe
from construction_financial_review.forecast_improvement_audit.decisions import build_decisions

from tests._fia_fixtures import minimal_inputs


def test_boe_contains_all_required_sections():
    inputs = minimal_inputs()
    decisions = build_decisions(inputs, {})
    md = boe.basis_of_estimate_md(inputs, {"package_stamp": "20260101_000000"}, decisions, True)
    for section in boe.BOE_SECTIONS:
        assert f"## {section}" in md, f"missing BOE section: {section}"
    # governance language present
    assert "FEE forecasts ARE capped by the projected budget value" in md
    assert "only hard floor" in md


def test_boe_coverage_shape_and_followup():
    from pathlib import Path
    cov = boe.coverage(minimal_inputs(), Path("/tmp/nonexistent_data_root"))
    assert cov["audit_package_has_formal_boe"] is True
    assert cov["boe_section_checklist"] == list(boe.BOE_SECTIONS)
    # discovered packages exist in discovery but their doc files don't -> follow-up flagged
    present = [p for p in cov["packages"] if p.get("present")]
    assert present and all(p["follow_up"] for p in present)
    assert all(p["formal_boe_present"] is False for p in present)
