"""Phase 08A agent policy validation + proof builders (Prompt 02 Addendum).

Validates the seeded agent registry against the agent registry, tool, and model
profile contracts, and builds the two deterministic evidence proofs
(`agent-registry-proof.json`, `agent-tool-policy-proof.json`). Read-only; no
external access, no writeback, no raw content. MCP is not implemented in 08A.
"""

from __future__ import annotations

from typing import Any

from ..contracts import load_phase_08a_contract
from .loader import load_agent_registry, load_model_profiles
from .models import AgentRegistry

# Review policies that keep high-impact / Tier 3 items under mandatory review.
_TIER3_AWARE_POLICIES = frozenset(
    {
        "tier_3_mandatory_review",
        "block_on_policy_failure",
        "no_high_impact_determinations",
        "tiered_review_required",
    }
)


def _load_contracts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_phase_08a_contract("agent_registry_contract"),
        load_phase_08a_contract("agent_tool_contract"),
        load_phase_08a_contract("model_profile_contract"),
    )


def validate_agent_registry(
    registry: AgentRegistry,
    *,
    registry_contract: dict[str, Any],
    tool_contract: dict[str, Any],
    model_profile_contract: dict[str, Any],
) -> dict[str, Any]:
    """Validate the registry against its contracts. Returns a structured report."""
    required_fields: list[str] = list(registry_contract.get("required_agent_fields", []))
    required_agents: list[str] = list(registry_contract.get("required_phase_08a_agents", []))
    valid_groups = set(tool_contract.get("tool_groups", {}).keys())
    global_deny = set(tool_contract.get("denied_tool_groups", []))
    profile_ids = {p.get("profile_id") for p in model_profile_contract.get("profiles", [])} | {
        "none"
    }

    violations: list[dict[str, str]] = []
    present_ids = {a.agent_id for a in registry.agents}
    missing_agents = [a for a in required_agents if a not in present_ids]
    for agent_id in missing_agents:
        violations.append(
            {
                "agent_id": agent_id,
                "code": "missing_required_agent",
                "detail": "required Phase 08A agent absent from registry",
            }
        )

    for agent in registry.agents:
        dumped = agent.model_dump()
        for field in required_fields:
            value = dumped.get(field)
            missing_value = value is None or (isinstance(value, str) and not value.strip())
            if field not in dumped or missing_value:
                violations.append(
                    {
                        "agent_id": agent.agent_id,
                        "code": "missing_required_field",
                        "detail": field,
                    }
                )

        if agent.agent_id in required_agents and not agent.enabled:
            violations.append(
                {
                    "agent_id": agent.agent_id,
                    "code": "required_agent_disabled",
                    "detail": "required agent must be enabled",
                }
            )

        allowed = set(agent.allowed_tool_groups)
        denied = set(agent.denied_tool_groups)
        for unknown in sorted(allowed - valid_groups):
            violations.append(
                {"agent_id": agent.agent_id, "code": "unknown_tool_group", "detail": unknown}
            )
        for overlap in sorted(allowed & denied):
            violations.append(
                {"agent_id": agent.agent_id, "code": "allowed_intersects_denied", "detail": overlap}
            )
        for leaked in sorted(allowed & global_deny):
            violations.append(
                {"agent_id": agent.agent_id, "code": "allowed_in_global_deny", "detail": leaked}
            )
        if agent.default_model_profile not in profile_ids:
            violations.append(
                {
                    "agent_id": agent.agent_id,
                    "code": "unknown_model_profile",
                    "detail": agent.default_model_profile,
                }
            )
        if not agent.receipt_required:
            violations.append(
                {
                    "agent_id": agent.agent_id,
                    "code": "receipt_not_required",
                    "detail": "receipt_required must be true",
                }
            )

    valid = not violations and not missing_agents
    return {
        "valid": valid,
        "agent_count": len(registry.agents),
        "enabled_count": sum(1 for a in registry.agents if a.enabled),
        "required_agents_present": not missing_agents,
        "missing_agents": missing_agents,
        "violations": violations,
    }


def build_agent_registry_proof() -> dict[str, Any]:
    """Deterministic proof for `agent-registry-proof.json`."""
    registry = load_agent_registry()
    registry_contract, tool_contract, model_profile_contract = _load_contracts()
    report = validate_agent_registry(
        registry,
        registry_contract=registry_contract,
        tool_contract=tool_contract,
        model_profile_contract=model_profile_contract,
    )

    field_codes = {"missing_required_field", "missing_required_agent", "required_agent_disabled"}
    all_fields_complete = not any(v["code"] in field_codes for v in report["violations"])
    model_profiles_explicit = not any(
        v["code"] == "unknown_model_profile" for v in report["violations"]
    ) and all(a.default_model_profile.strip() for a in registry.agents)
    receipts_required_all = all(a.receipt_required for a in registry.agents)
    triage = registry.by_id("review_triage_agent")
    tier3_visible = (
        any(a.review_policy in _TIER3_AWARE_POLICIES for a in registry.agents)
        and triage is not None
        and triage.review_policy == "tier_3_mandatory_review"
    )

    guardrails: dict[str, Any] = dict(registry_contract.get("guardrails", {}))
    guardrails["mcp_implemented"] = False

    return {
        "proof": "phase_08a_agent_registry",
        "proof_passed": report["valid"],
        "contract_version": registry_contract.get("version", "unknown"),
        "registry_version": registry.version,
        "agent_count": report["agent_count"],
        "enabled_count": report["enabled_count"],
        "required_agents_present": report["required_agents_present"],
        "missing_agents": report["missing_agents"],
        "all_fields_complete": all_fields_complete,
        "model_profiles_explicit": model_profiles_explicit,
        "receipts_required_all": receipts_required_all,
        "tier3_handling_visible": tier3_visible,
        "guardrails": guardrails,
        "violations": report["violations"],
    }


def build_agent_tool_policy_proof() -> dict[str, Any]:
    """Deterministic proof for `agent-tool-policy-proof.json`."""
    registry = load_agent_registry()
    tool_contract = load_phase_08a_contract("agent_tool_contract")
    valid_groups = set(tool_contract.get("tool_groups", {}).keys())
    global_deny = set(tool_contract.get("denied_tool_groups", []))

    per_agent: list[dict[str, Any]] = []
    violations: list[dict[str, str]] = []
    for agent in registry.agents:
        allowed = set(agent.allowed_tool_groups)
        denied = set(agent.denied_tool_groups)
        allowed_valid = allowed <= valid_groups
        no_denied_in_allowed = not (allowed & denied)
        no_global_deny_in_allowed = not (allowed & global_deny)
        if not allowed_valid:
            violations.append(
                {
                    "agent_id": agent.agent_id,
                    "code": "unknown_tool_group",
                    "detail": ",".join(sorted(allowed - valid_groups)),
                }
            )
        if not no_denied_in_allowed:
            violations.append(
                {
                    "agent_id": agent.agent_id,
                    "code": "allowed_intersects_denied",
                    "detail": ",".join(sorted(allowed & denied)),
                }
            )
        if not no_global_deny_in_allowed:
            violations.append(
                {
                    "agent_id": agent.agent_id,
                    "code": "allowed_in_global_deny",
                    "detail": ",".join(sorted(allowed & global_deny)),
                }
            )
        per_agent.append(
            {
                "agent_id": agent.agent_id,
                "allowed_tool_groups": sorted(allowed),
                "denied_tool_groups": sorted(denied),
                "allowed_valid": allowed_valid,
                "no_denied_in_allowed": no_denied_in_allowed,
                "no_global_deny_in_allowed": no_global_deny_in_allowed,
            }
        )

    return {
        "proof": "phase_08a_agent_tool_policy",
        "proof_passed": not violations,
        "contract_version": tool_contract.get("version", "unknown"),
        "denied_tool_groups_global": sorted(global_deny),
        "mcp_future_exposure_rule": tool_contract.get("mcp_future_exposure_rule", ""),
        "per_agent": per_agent,
        "violations": violations,
    }


# Model profile intent (Synthesized Prompt 03): deterministic router has no model;
# fast=Haiku, default=Sonnet, deep=Opus; evaluator emits checklist JSON.
_PROFILE_MODEL_INTENT: dict[str, str | None] = {
    "deterministic_router": None,
    "fast_summary": "claude-haiku-4-5",
    "default_reasoning": "claude-sonnet-4-6",
    "deep_reasoning": "claude-opus-4-8",
}
_PROFILE_OUTPUT_INTENT: dict[str, str] = {"evaluator": "checklist_json"}


def validate_model_profiles(seed: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the model-profiles seed against the model-profile contract."""
    contract_profiles = {
        p.get("profile_id"): p for p in contract.get("profiles", []) if p.get("profile_id")
    }
    seed_profiles: dict[str, Any] = seed.get("profiles", {}) or {}

    violations: list[dict[str, str]] = []
    missing_profiles = [pid for pid in contract_profiles if pid not in seed_profiles]
    for pid in missing_profiles:
        violations.append(
            {"profile_id": pid, "code": "missing_profile", "detail": "absent from seed"}
        )

    for pid, expected_model in _PROFILE_MODEL_INTENT.items():
        cp = contract_profiles.get(pid)
        sp = seed_profiles.get(pid)
        if cp is not None and cp.get("default_model") != expected_model:
            violations.append(
                {
                    "profile_id": pid,
                    "code": "contract_model_mismatch",
                    "detail": str(cp.get("default_model")),
                }
            )
        if sp is not None:
            if expected_model is None and sp.get("model") is not None:
                violations.append(
                    {
                        "profile_id": pid,
                        "code": "router_should_have_no_model",
                        "detail": str(sp.get("model")),
                    }
                )
            if expected_model is not None and sp.get("model") != expected_model:
                violations.append(
                    {
                        "profile_id": pid,
                        "code": "seed_model_mismatch",
                        "detail": str(sp.get("model")),
                    }
                )

    for pid, expected_output in _PROFILE_OUTPUT_INTENT.items():
        cp = contract_profiles.get(pid)
        sp = seed_profiles.get(pid)
        if cp is not None and cp.get("output_mode") != expected_output:
            violations.append(
                {
                    "profile_id": pid,
                    "code": "contract_output_mode_mismatch",
                    "detail": str(cp.get("output_mode")),
                }
            )
        if sp is not None and sp.get("output_mode") != expected_output:
            violations.append(
                {
                    "profile_id": pid,
                    "code": "seed_output_mode_mismatch",
                    "detail": str(sp.get("output_mode")),
                }
            )

    persistence = contract.get("persistence_policy", {})
    if persistence.get("persist_raw_prompt") is not False:
        violations.append(
            {"profile_id": "*", "code": "persist_raw_prompt_not_false", "detail": "contract"}
        )
    if persistence.get("persist_raw_response") is not False:
        violations.append(
            {"profile_id": "*", "code": "persist_raw_response_not_false", "detail": "contract"}
        )
    for pid, sp in seed_profiles.items():
        if sp.get("raw_prompt_persisted") is not False:
            violations.append(
                {"profile_id": pid, "code": "seed_raw_prompt_persisted", "detail": "must be false"}
            )
        if sp.get("raw_response_persisted") is not False:
            violations.append(
                {
                    "profile_id": pid,
                    "code": "seed_raw_response_persisted",
                    "detail": "must be false",
                }
            )

    return {
        "valid": not violations and not missing_profiles,
        "profile_count": len(seed_profiles),
        "missing_profiles": missing_profiles,
        "violations": violations,
    }


def build_agent_model_profile_proof() -> dict[str, Any]:
    """Deterministic proof for `agent-model-profile-proof.json`."""
    seed = load_model_profiles()
    contract = load_phase_08a_contract("model_profile_contract")
    report = validate_model_profiles(seed, contract)

    contract_profiles = {
        p.get("profile_id"): p for p in contract.get("profiles", []) if p.get("profile_id")
    }
    intent_map = {
        pid: {
            "default_model": contract_profiles.get(pid, {}).get("default_model"),
            "output_mode": contract_profiles.get(pid, {}).get("output_mode"),
        }
        for pid in contract_profiles
    }
    no_raw_persistence = not any(
        v["code"].endswith("persist_raw_prompt_not_false")
        or v["code"].endswith("persist_raw_response_not_false")
        or v["code"].startswith("seed_raw_")
        for v in report["violations"]
    )

    return {
        "proof": "phase_08a_agent_model_profile",
        "proof_passed": report["valid"],
        "contract_version": contract.get("version", "unknown"),
        "seed_version": seed.get("version", "unknown"),
        "profile_count": report["profile_count"],
        "intent_map": intent_map,
        "no_raw_persistence": no_raw_persistence,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
            "mcp_implemented": False,
        },
        "violations": report["violations"],
    }
