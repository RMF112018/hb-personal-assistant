"""Phase 10 local-AI contracts, seeds, and proof (declarative; no runtime yet).

Prompt 01 substrate: JSON contracts + YAML seed policies for local model profiles, AI jobs,
action candidates, follow-up watch, relationships, Obsidian vault management, Claude MCP packets,
the frontend review queue, and evaluation metrics — with Pydantic enforcement models and a
read-only contracts proof. No Ollama call, no DB schema, no job execution, no writeback here.
"""

from __future__ import annotations

from .ai_jobs import enqueue_ai_job_request, run_ai_jobs
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
from .fixture_runner import run_fixture_suite
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
from .provider import build_local_model_status
from .raw_action_intelligence import (
    extract_action_candidates_from_raw,
)
from .raw_context import (
    build_raw_calendar_context_packet,
    build_raw_email_context_packet,
)
from .structured_output import (
    GenerationBackend,
    StaticOutputClient,
    StructuredOutputClient,
    StructuredOutputResult,
    action_candidate_dict_from_fixture,
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
    # Prompt 03: local model readiness status (probe-only)
    "build_local_model_status",
    # Prompt 04: schema-enforced structured-output client + hash-only receipts
    "StructuredOutputClient",
    "StructuredOutputResult",
    "StaticOutputClient",
    "GenerationBackend",
    "action_candidate_dict_from_fixture",
    # Prompt 05: AI job queue enqueue + run lifecycle (no-overlap, retry/backoff, receipts)
    "enqueue_ai_job_request",
    "run_ai_jobs",
    # Prompt 06: action candidate fixture suite runner (batch validation/regression harness)
    "run_fixture_suite",
]
