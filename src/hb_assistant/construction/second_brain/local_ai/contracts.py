"""Phase 10 Prompt 01 — local-AI contract registry + fail-closed seed loaders.

Read-only. Registers the ten Phase 10 JSON contracts (reusing the second-brain
``_load_json_resource`` packaged-resource loader) and loads the four YAML seed policies into
their Pydantic models. Fail-closed: a missing/invalid seed raises :class:`Phase10ContractError`
rather than returning a silent default. No DB access, no external calls, no writeback.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from ..contracts import _load_json_resource
from .models import (
    AiJobPolicy,
    LocalModelProfiles,
    McpPacketPolicy,
    ObsidianVaultPolicy,
    RawContentPolicy,
)

# Logical name -> packaged JSON filename (src/hb_assistant/resources/json/).
PHASE_10_CONTRACT_FILES: dict[str, str] = {
    "local_model_profile_contract": "phase_10_local_model_profile_contract.json",
    "ai_job_contract": "phase_10_ai_job_contract.json",
    "action_candidate_output_schema": "phase_10_action_candidate_output_schema.json",
    "daily_brief_action_candidate_contract": "phase_10_daily_brief_action_candidate_contract.json",
    "claude_mcp_packet_contract": "phase_10_claude_mcp_packet_contract.json",
    "obsidian_vault_manager_contract": "phase_10_obsidian_vault_manager_contract.json",
    "follow_up_watch_contract": "phase_10_follow_up_watch_contract.json",
    "relationship_candidate_contract": "phase_10_relationship_candidate_contract.json",
    "evaluation_metrics_contract": "phase_10_evaluation_metrics_contract.json",
    "frontend_review_queue_contract": "phase_10_frontend_review_queue_contract.json",
    "email_task_signal_contract": "phase_10_email_task_signal_contract.json",
    "raw_content_policy_contract": "phase_10a_raw_content_policy_contract.json",
    "raw_content_api_response_contract": "raw_content_api_response_contract.json",
}

# Logical name -> (repo-root seed filename, env override var, Pydantic model).
PHASE_10_SEED_FILES: dict[str, str] = {
    "local_model_profiles": "phase_10_local_model_profiles.seed.yaml",
    "ai_job_policy": "phase_10_ai_job_policy.seed.yaml",
    "obsidian_vault_policy": "phase_10_obsidian_vault_policy.seed.yaml",
    "mcp_packet_policy": "phase_10_mcp_packet_policy.seed.yaml",
    "raw_content_policy": "phase_10a_raw_content_policy.seed.yaml",
}

_SEED_ENV_VARS: dict[str, str] = {
    "local_model_profiles": "HB_PHASE_10_LOCAL_MODEL_PROFILES",
    "ai_job_policy": "HB_PHASE_10_AI_JOB_POLICY",
    "obsidian_vault_policy": "HB_PHASE_10_OBSIDIAN_VAULT_POLICY",
    "mcp_packet_policy": "HB_PHASE_10_MCP_PACKET_POLICY",
    "raw_content_policy": "HB_PHASE_10_RAW_CONTENT_POLICY",
}


class Phase10ContractError(RuntimeError):
    """Raised when a Phase 10 contract or seed cannot be resolved/validated (fail-closed)."""


def load_phase_10_contract(name: str) -> dict[str, Any]:
    """Load a single Phase 10 JSON contract by logical name (fail-closed)."""
    if name not in PHASE_10_CONTRACT_FILES:
        raise KeyError(f"unknown phase 10 contract: {name!r}")
    parsed = _load_json_resource(PHASE_10_CONTRACT_FILES[name])
    if not parsed:
        raise Phase10ContractError(f"phase 10 contract {name!r} is missing or empty")
    return parsed


def load_all_phase_10_contracts() -> dict[str, dict[str, Any]]:
    """Load every registered Phase 10 contract (logical name -> parsed dict)."""
    return {name: load_phase_10_contract(name) for name in PHASE_10_CONTRACT_FILES}


def _seed_path(name: str) -> Path:
    env_override = os.environ.get(_SEED_ENV_VARS[name])
    if env_override:
        return Path(env_override).expanduser()
    return PathPolicy().resolve_repo_root() / "resources" / "config" / PHASE_10_SEED_FILES[name]


def _load_seed_dict(name: str) -> dict[str, Any]:
    if name not in PHASE_10_SEED_FILES:
        raise KeyError(f"unknown phase 10 seed: {name!r}")
    path = _seed_path(name)
    if not path.exists():
        raise Phase10ContractError(f"phase 10 seed {name!r} not found at {path}")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise Phase10ContractError(f"phase 10 seed {name!r} is not a mapping")
    return parsed


def load_local_model_profiles() -> LocalModelProfiles:
    """Load + validate the local model profile tiers (fail-closed)."""
    return LocalModelProfiles.model_validate(_load_seed_dict("local_model_profiles"))


def load_ai_job_policy() -> AiJobPolicy:
    """Load + validate the AI job policy (fail-closed)."""
    return AiJobPolicy.model_validate(_load_seed_dict("ai_job_policy"))


def load_obsidian_vault_policy() -> ObsidianVaultPolicy:
    """Load + validate the Obsidian vault policy (fail-closed)."""
    return ObsidianVaultPolicy.model_validate(_load_seed_dict("obsidian_vault_policy"))


def load_mcp_packet_policy() -> McpPacketPolicy:
    """Load + validate the MCP packet policy (fail-closed)."""
    return McpPacketPolicy.model_validate(_load_seed_dict("mcp_packet_policy"))


def load_raw_content_policy() -> RawContentPolicy:
    """Load + validate the raw content policy (Phase 10A Prompt 01; fail-closed)."""
    return RawContentPolicy.model_validate(_load_seed_dict("raw_content_policy"))


def load_raw_content_api_response_contract() -> dict[str, Any]:
    """Load the Phase 10A raw content API response contract (shapes for include vs metadata modes)."""
    return load_phase_10_contract("raw_content_api_response_contract")
