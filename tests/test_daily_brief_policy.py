"""Phase 08A Prompt 11 — daily-brief policy seed + contract validation."""

from __future__ import annotations

from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.daily_brief import (
    load_daily_brief_policy_seed,
    reason_code_for_tier,
    validate_daily_brief_policy,
)
from hb_assistant.construction.second_brain.daily_brief.models import HANDOFF_SECTIONS


def test_seed_loads_with_version_and_triage_order() -> None:
    seed = load_daily_brief_policy_seed()
    assert seed["version"].startswith("phase_08a_daily_brief_policy")
    assert seed["brief_assembly"]["dry_run_first"] is True
    assert seed["brief_assembly"]["render_html"] is False
    assert seed["brief_assembly"]["emit_notifications"] is False
    assert seed["triage_prioritization"]["order"][0] == "review_tier"


def test_contract_required_keys_and_sections() -> None:
    contract = load_phase_08a_contract("daily_brief_contract")
    for key in ("version", "required_fields", "brief_sections", "guardrails"):
        assert key in contract
    assert set(HANDOFF_SECTIONS) <= set(contract["brief_sections"])
    assert "source_coverage" in contract["required_fields"]
    assert "review_tier_counts" in contract["required_fields"]
    g = contract["guardrails"]
    assert g["no_html"] is True
    assert g["no_notifications"] is True
    assert g["tier_3_never_final_conclusion"] is True


def test_policy_validation_passes() -> None:
    result = validate_daily_brief_policy()
    assert result["valid"] is True, result["violations"]


def test_reason_code_for_tier_defaults_to_mandatory_review() -> None:
    assert reason_code_for_tier(1) == "T1_SOURCE_BACKED"
    assert reason_code_for_tier(2) == "T2_REVIEW_RECOMMENDED"
    assert reason_code_for_tier(3) == "T3_MANDATORY_REVIEW"
    assert reason_code_for_tier(99) == "T3_MANDATORY_REVIEW"
