"""Phase 10 local-AI contracts, seeds, and proof (declarative; no runtime yet).

Prompt 01 substrate: JSON contracts + YAML seed policies for local model profiles, AI jobs,
action candidates, follow-up watch, relationships, Obsidian vault management, Claude MCP packets,
the frontend review queue, and evaluation metrics — with Pydantic enforcement models and a
read-only contracts proof. No Ollama call, no DB schema, no job execution, no writeback here.
"""

from __future__ import annotations

from .contracts import (
    PHASE_10_CONTRACT_FILES,
    PHASE_10_SEED_FILES,
    Phase10ContractError,
    load_ai_job_policy,
    load_all_phase_10_contracts,
    load_local_model_profiles,
    load_mcp_packet_policy,
    load_obsidian_vault_policy,
    load_phase_10_contract,
    load_raw_content_policy,
)
from .models import (
    HIGH_STAKES_CATEGORIES,
    ActionCandidate,
    AiJobPolicy,
    LocalModelProfile,
    LocalModelProfiles,
    McpPacketPolicy,
    ObsidianVaultPolicy,
    RawContentPolicy,
)
from .proof import Phase10ProofError, build_phase_10_contracts_proof
from .raw_action_intelligence import (
    extract_action_candidates_from_raw,
)
from .raw_context import (
    build_raw_calendar_context_packet,
    build_raw_email_context_packet,
)

__all__ = [
    "PHASE_10_CONTRACT_FILES",
    "PHASE_10_SEED_FILES",
    "Phase10ContractError",
    "Phase10ProofError",
    "ActionCandidate",
    "AiJobPolicy",
    "LocalModelProfile",
    "LocalModelProfiles",
    "McpPacketPolicy",
    "ObsidianVaultPolicy",
    "HIGH_STAKES_CATEGORIES",
    "build_phase_10_contracts_proof",
    "load_all_phase_10_contracts",
    "load_phase_10_contract",
    "load_local_model_profiles",
    "load_ai_job_policy",
    "load_obsidian_vault_policy",
    "load_mcp_packet_policy",
    "load_raw_content_policy",
    "RawContentPolicy",
    # Prompt 06 raw model context packets (actual content, bounded, source-referenced)
    "build_raw_email_context_packet",
    "build_raw_calendar_context_packet",
    # Prompt 07: action intelligence from raw content (strict schema + business contract + retry/repair)
    "extract_action_candidates_from_raw",
]
