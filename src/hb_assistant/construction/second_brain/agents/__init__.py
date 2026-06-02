"""Phase 08A agent runtime foundation (Prompt 02 Addendum).

Registry contract + seed loader, internal AgentResult / AgentRunReceipt
structures, and agent policy validation for the nine Phase 08A internal service
agents (A01-A09). Foundation only: no agent executes, nothing is persisted, and
MCP is not implemented (deferred to Phase 08D).
"""

from __future__ import annotations

from .loader import (
    AgentRegistryError,
    ModelProfilesError,
    load_agent_registry,
    load_model_profiles,
)
from .models import AgentDefinition, AgentRegistry, AgentResult, AgentRunReceipt
from .policy import (
    build_agent_model_profile_proof,
    build_agent_registry_proof,
    build_agent_tool_policy_proof,
    validate_agent_registry,
    validate_model_profiles,
)

__all__ = [
    "AgentRegistryError",
    "ModelProfilesError",
    "load_agent_registry",
    "load_model_profiles",
    "AgentDefinition",
    "AgentRegistry",
    "AgentResult",
    "AgentRunReceipt",
    "build_agent_model_profile_proof",
    "build_agent_registry_proof",
    "build_agent_tool_policy_proof",
    "validate_agent_registry",
    "validate_model_profiles",
]
