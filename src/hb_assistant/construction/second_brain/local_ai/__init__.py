"""Phase 10 local-AI contracts, seeds, and proof (declarative; no runtime yet).

Prompt 01 substrate: JSON contracts + YAML seed policies for local model profiles, AI jobs,
action candidates, follow-up watch, relationships, Obsidian vault management, Claude MCP packets,
the frontend review queue, and evaluation metrics — with Pydantic enforcement models and a
read-only contracts proof. No Ollama call, no DB schema, no job execution, no writeback here.
"""

from __future__ import annotations

from .ai_jobs import enqueue_ai_job_request, run_ai_jobs
from .batch_extraction import (
    UnsupportedBatchSourceError,
    run_batch_extraction,
)
from .calendar_prep import build_calendar_prep_candidates
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
from .daily_brief_render import render_daily_brief, write_rendered_brief_to_path
from .daily_brief_synthesis import build_daily_brief_candidates
from .email_task_extraction import (
    extract_email_task_candidates,
    score_email_task_signals,
)
from .fixture_runner import run_fixture_suite
from .follow_up_watch import (
    classify_watch_status,
    run_follow_up_watch_scan,
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
from .packet_builders import (
    build_calendar_event_action_packet,
    build_email_thread_action_packet,
    build_related_context_action_packet,
    build_triage_batch_packet,
)
from .packet_normalize import has_join_url, normalize_model_text, summarize_attendees
from .pipeline import run_local_agent_pipeline
from .procore_digest import build_procore_action_digest
from .proof import Phase10ProofError, build_phase_10_contracts_proof
from .provider import build_local_model_status, resolve_local_model_client
from .raw_action_intelligence import (
    extract_action_candidates_from_raw,
    extract_actions_for_packet,
)
from .raw_context import (
    build_raw_calendar_context_packet,
    build_raw_email_context_packet,
)
from .relationship_scoring import (
    find_email_calendar_relationships,
    score_email_calendar_relationship,
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
    # Prompt 07: email task candidate extraction (deterministic signals over thread summaries)
    "extract_email_task_candidates",
    "score_email_task_signals",
    # Phase 10A: bounded purposeful packets + deterministic relationship scoring
    "build_email_thread_action_packet",
    "build_calendar_event_action_packet",
    "build_related_context_action_packet",
    "build_triage_batch_packet",
    "normalize_model_text",
    "has_join_url",
    "summarize_attendees",
    "score_email_calendar_relationship",
    "find_email_calendar_relationships",
    "extract_actions_for_packet",
    "resolve_local_model_client",
    "run_batch_extraction",
    "UnsupportedBatchSourceError",
    # Phase 10: deterministic follow-up watch monitor (advisory, no writeback)
    "classify_watch_status",
    "run_follow_up_watch_scan",
    # Phase 10: deterministic Procore action-signal digest (advisory, no writeback)
    "build_procore_action_digest",
    # Phase 10: deterministic calendar meeting-prep candidates (advisory, no writeback)
    "build_calendar_prep_candidates",
    # Phase 10: daily-brief candidate synthesis (unifies email + Procore + calendar families)
    "build_daily_brief_candidates",
    # Phase 10: daily-brief rendering / consumption (read-only render + path-safe write)
    "render_daily_brief",
    "write_rendered_brief_to_path",
    # Phase 10: local-agent pipeline orchestration (one repeatable daily run)
    "run_local_agent_pipeline",
]
