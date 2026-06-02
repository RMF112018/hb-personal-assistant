"""Phase 08A Prompt 02 — second-brain contract loader + contract content guarantees.

Mirrors test_phase_07d_contracts.py: every registered Phase 08A contract loads, carries
its required keys + a version, and contains no raw URL / token / PEM / JWT leakage.
Adds posture assertions from the Final-Update operating model: Tier 3 is never an accepted
fact / never auto-accepted; sensitive/high-impact defaults to mandatory review; memory
proposals default to review-required with no silent acceptance; source references forbid
raw URLs/tokens/bodies.
"""

from __future__ import annotations

import json
import re

import pytest

from hb_assistant.construction.second_brain import (
    PHASE_08A_CONTRACT_FILES,
    load_all_phase_08a_contracts,
    load_phase_08a_contract,
)

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}",
    re.IGNORECASE,
)

_REQUIRED_KEYS = {
    "second_brain_runtime_contract": ["version", "components", "mode_values", "guardrails"],
    "source_reference_contract": ["version", "required_fields", "forbidden_fields"],
    "long_term_memory_contract": ["version", "required_fields", "review_required_for"],
    "memory_update_candidate_contract": [
        "version",
        "statuses",
        "default_review_required",
        "silent_acceptance_allowed",
    ],
    "research_packet_contract": ["version", "required_fields", "degradation_modes", "guardrails"],
    "evaluation_criteria_contract": ["version", "checklist_items", "score_range", "guardrails"],
    "operator_feedback_contract": ["version", "feedback_classes", "required_fields", "guardrails"],
    "operator_preference_profile_contract": ["version", "scopes", "required_fields", "guardrails"],
    "review_tier_contract": ["version", "tiers", "reason_codes", "mandatory_review_for"],
    "memory_quality_signal_contract": ["version", "signal_types", "required_fields", "guardrails"],
    # Phase 08A Prompt 02 Addendum — agent runtime foundation contracts.
    "agent_registry_contract": [
        "version",
        "required_agent_fields",
        "required_phase_08a_agents",
        "guardrails",
    ],
    "agent_tool_contract": [
        "version",
        "tool_groups",
        "denied_tool_groups",
        "mcp_future_exposure_rule",
    ],
    "model_profile_contract": ["version", "profiles", "persistence_policy"],
    # Phase 08A Prompt 04 — retrieval policy + context budget contracts.
    "retrieval_policy_contract": ["version", "required_fields", "excluded"],
    "context_budget_contract": ["version", "required_fields"],
    # Phase 08A Prompt 05 — approved Obsidian index manifest contract.
    "obsidian_index_manifest_contract": ["version", "required_fields"],
}


def test_all_contracts_load_non_empty() -> None:
    contracts = load_all_phase_08a_contracts()
    assert set(contracts) == set(PHASE_08A_CONTRACT_FILES)
    for name, body in contracts.items():
        assert body, f"{name} loaded empty"


@pytest.mark.parametrize("name", sorted(PHASE_08A_CONTRACT_FILES))
def test_required_keys_and_version(name: str) -> None:
    c = load_phase_08a_contract(name)
    assert isinstance(c.get("version"), str) and c["version"]
    for key in _REQUIRED_KEYS[name]:
        assert key in c, f"{name} missing required key {key}"


@pytest.mark.parametrize("name", sorted(PHASE_08A_CONTRACT_FILES))
def test_contracts_are_identifier_only_no_leaks(name: str) -> None:
    blob = json.dumps(load_phase_08a_contract(name), default=str)
    assert _LEAK.search(blob) is None, f"{name} contains a leak-pattern value"


def test_unknown_contract_name_raises() -> None:
    with pytest.raises(KeyError):
        load_phase_08a_contract("does_not_exist")


def test_review_tier_contract_tier3_never_accepted_fact() -> None:
    c = load_phase_08a_contract("review_tier_contract")
    assert c["tier_3_is_accepted_fact"] is False
    assert "tier_3" in c["never_auto_accept_tiers"]
    assert c["tiers"]["tier_3"]["auto_accept_as_fact"] is False
    assert c["guardrails"]["tier_3_never_auto_accepted"] is True


def test_review_tier_contract_sensitive_mandatory_review() -> None:
    c = load_phase_08a_contract("review_tier_contract")
    assert "sensitive_high_impact" in c["mandatory_review_for"]
    assert c["guardrails"]["sensitive_high_impact_defaults_to_mandatory_review"] is True
    # Every reason code maps to a defined tier.
    valid = set(c["tiers"])
    assert all(v in valid for v in c["reason_codes"].values())


def test_memory_candidate_contract_defaults_review_required_no_silent_accept() -> None:
    c = load_phase_08a_contract("memory_update_candidate_contract")
    assert c["default_review_required"] is True
    assert c["silent_acceptance_allowed"] is False


def test_source_reference_contract_forbids_raw_urls_and_tokens() -> None:
    c = load_phase_08a_contract("source_reference_contract")
    forbidden = set(c["forbidden_fields"])
    assert {"signed_url", "download_url", "token", "secret", "raw_body"} <= forbidden


def test_runtime_contract_denies_model_external_access_and_writeback() -> None:
    g = load_phase_08a_contract("second_brain_runtime_contract")["guardrails"]
    assert g["model_direct_external_api_access"] is False
    assert g["external_writeback"] is False
    assert g["local_first"] is True
