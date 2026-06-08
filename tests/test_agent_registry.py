"""Phase 08A Prompt 02 Addendum — agent registry, policy, proofs (offline).

Proves the nine required A01-A09 agents load and validate against the registry/tool/
model profile contracts, that tool allow/deny rules hold, that both evidence proofs
pass, and that nothing leaks raw content. The registry is intentionally extensible
(the contract's required set is a subset check); Phase 10 adds three local-agent-family
entries, so the seed now carries 12 agents while still containing all 9 required ones.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hb_assistant.construction.second_brain.agents import (
    AgentRegistry,
    AgentRegistryError,
    build_agent_registry_proof,
    build_agent_tool_policy_proof,
    load_agent_registry,
    load_model_profiles,
    validate_agent_registry,
)
from hb_assistant.construction.second_brain.agents import loader as loader_mod
from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract

_REQUIRED_AGENTS = {
    "second_brain_orchestrator_agent",
    "research_packet_agent",
    "retrieval_source_broker_agent",
    "answer_synthesis_agent",
    "output_evaluation_agent",
    "daily_brief_agent",
    "memory_curator_agent",
    "operator_preference_agent",
    "review_triage_agent",
}


_PHASE_10_FAMILY_AGENTS = {
    "email_action_extraction_agent",
    "follow_up_watch_agent",
    "procore_digest_agent",
}
_EXPECTED_AGENTS = _REQUIRED_AGENTS | _PHASE_10_FAMILY_AGENTS


def test_seed_loads_expected_enabled_agents() -> None:
    reg = load_agent_registry()
    assert reg.version == "phase_08a_agent_registry-v1"
    assert len(reg.agents) == 12
    ids = {a.agent_id for a in reg.agents}
    assert ids == _EXPECTED_AGENTS
    assert _REQUIRED_AGENTS <= ids  # all 9 required still present (subset check)
    assert all(a.enabled for a in reg.agents)
    assert all(a.receipt_required for a in reg.agents)
    assert all(a.output_contract for a in reg.agents)


def test_model_profiles_seed_loads() -> None:
    profiles = load_model_profiles()
    assert profiles["version"] == "phase_08a_model_profiles-v1"
    assert len(profiles["profiles"]) == 5
    for prof in profiles["profiles"].values():
        assert prof["raw_prompt_persisted"] is False
        assert prof["raw_response_persisted"] is False


def test_registry_validates_against_contracts() -> None:
    reg = load_agent_registry()
    report = validate_agent_registry(
        reg,
        registry_contract=load_phase_08a_contract("agent_registry_contract"),
        tool_contract=load_phase_08a_contract("agent_tool_contract"),
        model_profile_contract=load_phase_08a_contract("model_profile_contract"),
    )
    assert report["valid"] is True
    assert report["violations"] == []
    assert report["missing_agents"] == []
    assert report["agent_count"] == 12
    assert report["enabled_count"] == 12


def test_no_agent_allows_a_globally_denied_or_self_denied_group() -> None:
    reg = load_agent_registry()
    tool = load_phase_08a_contract("agent_tool_contract")
    valid_groups = set(tool["tool_groups"])
    global_deny = set(tool["denied_tool_groups"])
    for agent in reg.agents:
        allowed = set(agent.allowed_tool_groups)
        assert allowed <= valid_groups, f"{agent.agent_id} allows unknown group"
        assert not (allowed & global_deny), f"{agent.agent_id} allows a globally-denied group"
        assert not (allowed & set(agent.denied_tool_groups))


def test_default_model_profiles_are_known() -> None:
    reg = load_agent_registry()
    profile_ids = {
        p["profile_id"] for p in load_phase_08a_contract("model_profile_contract")["profiles"]
    }
    profile_ids.add("none")
    for agent in reg.agents:
        assert agent.default_model_profile in profile_ids


def test_registry_proof_passes() -> None:
    proof = build_agent_registry_proof()
    assert proof["proof"] == "phase_08a_agent_registry"
    assert proof["proof_passed"] is True
    assert proof["agent_count"] == 12
    assert proof["required_agents_present"] is True
    assert proof["all_fields_complete"] is True
    assert proof["model_profiles_explicit"] is True
    assert proof["receipts_required_all"] is True
    assert proof["tier3_handling_visible"] is True
    assert proof["guardrails"]["mcp_implemented"] is False
    assert proof["guardrails"]["no_external_writeback"] is True
    assert proof["violations"] == []


def test_tool_policy_proof_passes() -> None:
    proof = build_agent_tool_policy_proof()
    assert proof["proof"] == "phase_08a_agent_tool_policy"
    assert proof["proof_passed"] is True
    assert len(proof["per_agent"]) == 12
    assert "external_writeback" in proof["denied_tool_groups_global"]
    for entry in proof["per_agent"]:
        assert entry["allowed_valid"] is True
        assert entry["no_denied_in_allowed"] is True
        assert entry["no_global_deny_in_allowed"] is True
    assert proof["violations"] == []


def test_proofs_carry_no_raw_content() -> None:
    blob = json.dumps(build_agent_registry_proof()) + json.dumps(build_agent_tool_policy_proof())
    for forbidden in (
        "signed_url",
        "download_url",
        "raw_body",
        "raw_prompt",
        "raw_response",
        "token",
        "secret",
    ):
        assert forbidden not in blob


def test_duplicate_agent_id_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentRegistry.model_validate(
            {
                "version": "x",
                "agents": [
                    {
                        "agent_id": "dup",
                        "phase_owner": "08A",
                        "enabled": True,
                        "purpose": "p",
                        "allowed_tool_groups": ["status"],
                        "denied_tool_groups": [],
                        "default_model_profile": "none",
                        "review_policy": "advisory_only",
                        "output_contract": "agent_result",
                        "receipt_required": True,
                    },
                    {
                        "agent_id": "dup",
                        "phase_owner": "08A",
                        "enabled": True,
                        "purpose": "p",
                        "allowed_tool_groups": ["status"],
                        "denied_tool_groups": [],
                        "default_model_profile": "none",
                        "review_policy": "advisory_only",
                        "output_contract": "agent_result",
                        "receipt_required": True,
                    },
                ],
            }
        )


def test_validation_flags_unknown_tool_group_and_profile() -> None:
    reg = AgentRegistry.model_validate(
        {
            "version": "x",
            "agents": [
                {
                    "agent_id": "bad_agent",
                    "phase_owner": "08A",
                    "enabled": True,
                    "purpose": "p",
                    "allowed_tool_groups": ["not_a_real_group", "external_writeback"],
                    "denied_tool_groups": [],
                    "default_model_profile": "made_up_profile",
                    "review_policy": "advisory_only",
                    "output_contract": "agent_result",
                    "receipt_required": True,
                }
            ],
        }
    )
    report = validate_agent_registry(
        reg,
        registry_contract=load_phase_08a_contract("agent_registry_contract"),
        tool_contract=load_phase_08a_contract("agent_tool_contract"),
        model_profile_contract=load_phase_08a_contract("model_profile_contract"),
    )
    assert report["valid"] is False
    codes = {v["code"] for v in report["violations"]}
    assert "unknown_tool_group" in codes
    assert "allowed_in_global_deny" in codes
    assert "unknown_model_profile" in codes
    assert "missing_required_agent" in codes  # required agents absent


def test_env_var_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "override.yaml"
    override.write_text(
        "version: override-v1\n"
        "agents:\n"
        "  - agent_id: solo_agent\n"
        "    phase_owner: '08A'\n"
        "    enabled: true\n"
        "    purpose: p\n"
        "    allowed_tool_groups: [status]\n"
        "    denied_tool_groups: []\n"
        "    default_model_profile: none\n"
        "    review_policy: advisory_only\n"
        "    output_contract: agent_result\n"
        "    receipt_required: true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(loader_mod.REGISTRY_ENV_VAR, str(override))
    reg = load_agent_registry()
    assert reg.version == "override-v1"
    assert len(reg.agents) == 1


def test_missing_seed_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point repo root at an empty dir so the seed is absent.
    from hb_assistant.config import path_policy as pp_mod

    monkeypatch.setattr(pp_mod.PathPolicy, "resolve_repo_root", lambda self: tmp_path)
    with pytest.raises(AgentRegistryError):
        load_agent_registry()
