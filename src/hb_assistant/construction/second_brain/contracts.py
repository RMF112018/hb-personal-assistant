"""Phase 08A second-brain machine-readable contracts (loader + registry).

Mirrors ``construction/relationships/contracts.py``. Read-only: loads the packaged JSON
contracts that describe the V26 second-brain schema and the research -> evaluation ->
synthesis -> capture pipeline (review tiers, research packets, evaluation criteria,
operator feedback, preference profiles, memory quality signals). No runtime behavior, no
external API access, no writeback.

Only the foundational + addendum contracts whose entities land in the V26 migration are
registered here. Feature-specific contracts (retrieval policy, obsidian index manifest,
query-tool allowlist, interactive query, chat session memory, daily brief, 08A data
quality gates, 08A validation matrix) are installed by their owning later 08A prompts so
the repo never ships a contract implying an unsupported runtime surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import shim
    import importlib.resources as importlib_resources
except Exception:  # pragma: no cover
    import importlib_resources  # type: ignore[no-redef]

_CONTRACT_PKG = "hb_assistant.resources.json"

PHASE_08A_CONTRACT_FILES: dict[str, str] = {
    "second_brain_runtime_contract": "second_brain_runtime_contract.json",
    "source_reference_contract": "source_reference_contract.json",
    "long_term_memory_contract": "long_term_memory_contract.json",
    "memory_update_candidate_contract": "memory_update_candidate_contract.json",
    "research_packet_contract": "research_packet_contract.json",
    "evaluation_criteria_contract": "evaluation_criteria_contract.json",
    "operator_feedback_contract": "operator_feedback_contract.json",
    "operator_preference_profile_contract": "operator_preference_profile_contract.json",
    "review_tier_contract": "review_tier_contract.json",
    "memory_quality_signal_contract": "memory_quality_signal_contract.json",
    # Phase 08A Prompt 02 Addendum — agent runtime foundation contracts.
    "agent_registry_contract": "phase_08a_agent_registry_contract.json",
    "agent_tool_contract": "phase_08a_agent_tool_contract.json",
    "model_profile_contract": "phase_08a_model_profile_contract.json",
    # Phase 08A Prompt 04 — retrieval policy + context budget contracts.
    "retrieval_policy_contract": "retrieval_policy_contract.json",
    "context_budget_contract": "context_budget_contract.json",
    # Phase 08A Prompt 05 — approved Obsidian index manifest contract.
    "obsidian_index_manifest_contract": "obsidian_index_manifest_contract.json",
    # Phase 08A Prompt 06 — allowlisted read-only SQLite query-tool contract.
    "sqlite_query_tool": "sqlite_query_tool_contract.json",
    # Phase 08A Prompt 08 — interactive query output contract.
    "interactive_query_contract": "interactive_query_contract.json",
    # Phase 08A Prompt 11 — daily-brief context + delivery handoff contract.
    "daily_brief_contract": "daily_brief_contract.json",
    # Phase 08A Prompt 14 — second-brain data-quality gate set.
    "data_quality_gates_contract": "phase_08a_data_quality_gates.json",
}

# Phase 08B contracts (Automation Delivery & Observability). Registered separately so the 08A
# loader/registry stays unchanged; additive only.
PHASE_08B_CONTRACT_FILES: dict[str, str] = {
    # Phase 08B Prompt 02 — persisted agent receipts, gate set, automation policy.
    "agent_receipts_contract": "phase_08b_agent_receipts_contract.json",
    "data_quality_gates_contract": "phase_08b_data_quality_gates.json",
    "automation_policy_contract": "phase_08b_automation_policy_contract.json",
    # Phase 08B Addendum Prompt 01 — executor policy, stages, safe replay, execution gate, validation matrix (declarative substrate only; executor impl deferred).
    "automation_executor_contract": "phase_08b_automation_executor_contract.json",
    "executor_stage_contract": "phase_08b_executor_stage_contract.json",
    "safe_replay_contract": "phase_08b_safe_replay_contract.json",
    "automation_execution_gate_contract": "phase_08b_automation_execution_gate_contract.json",
    "executor_validation_matrix": "phase_08b_executor_validation_matrix.json",
}


def _load_json_resource(filename: str) -> dict[str, Any]:
    """Load a packaged json resource. importlib -> filesystem -> empty dict."""
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(_CONTRACT_PKG) / filename).read_text(encoding="utf-8")
        else:  # pragma: no cover - legacy importlib path
            text = importlib_resources.read_text(_CONTRACT_PKG, filename, encoding="utf-8")
        parsed = json.loads(text)
    except Exception:
        candidate = Path(__file__).resolve().parents[2] / "resources" / "json" / filename
        if candidate.exists():
            parsed = json.loads(candidate.read_text(encoding="utf-8"))
        else:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def load_phase_08a_contract(name: str) -> dict[str, Any]:
    """Load a single Phase 08A contract by logical name."""
    if name not in PHASE_08A_CONTRACT_FILES:
        raise KeyError(f"unknown phase 08A contract: {name!r}")
    return _load_json_resource(PHASE_08A_CONTRACT_FILES[name])


def load_all_phase_08a_contracts() -> dict[str, dict[str, Any]]:
    """Load every registered Phase 08A contract (logical name -> parsed dict)."""
    return {name: load_phase_08a_contract(name) for name in PHASE_08A_CONTRACT_FILES}


def load_phase_08b_contract(name: str) -> dict[str, Any]:
    """Load a single Phase 08B contract by logical name."""
    if name not in PHASE_08B_CONTRACT_FILES:
        raise KeyError(f"unknown phase 08B contract: {name!r}")
    return _load_json_resource(PHASE_08B_CONTRACT_FILES[name])


def load_all_phase_08b_contracts() -> dict[str, dict[str, Any]]:
    """Load every registered Phase 08B contract (logical name -> parsed dict)."""
    return {name: load_phase_08b_contract(name) for name in PHASE_08B_CONTRACT_FILES}

# Phase 08C contracts (Financial Fact Normalization and Readiness). Registered separately.
PHASE_08C_CONTRACT_FILES: dict[str, str] = {
    "data_quality_gates_contract": "phase_08c_data_quality_gates_contract.json",
    "financial_fact_contract": "phase_08c_financial_fact_contract.json",
    "amount_normalization_contract": "phase_08c_amount_normalization_contract.json",
    "currency_completeness_contract": "phase_08c_currency_completeness_contract.json",
    "wbs_cost_code_completeness_contract": "phase_08c_wbs_cost_code_completeness_contract.json",
    "financial_source_coverage_contract": "phase_08c_financial_source_coverage_contract.json",
    "exposure_summary_contract": "phase_08c_exposure_summary_contract.json",
    "forecast_readiness_contract": "phase_08c_forecast_readiness_contract.json",
    "review_required_financial_policy_contract": "phase_08c_review_required_financial_policy_contract.json",
    "validation_matrix": "phase_08c_validation_matrix.json",
}

def load_phase_08c_contract(name: str) -> dict[str, Any]:
    """Load a single Phase 08C contract by logical name."""
    if name not in PHASE_08C_CONTRACT_FILES:
        raise KeyError(f"unknown phase 08C contract: {name!r}")
    return _load_json_resource(PHASE_08C_CONTRACT_FILES[name])

def load_all_phase_08c_contracts() -> dict[str, dict[str, Any]]:
    """Load every registered Phase 08C contract (logical name -> parsed dict)."""
    return {name: load_phase_08c_contract(name) for name in PHASE_08C_CONTRACT_FILES}

# Phase 08D contracts (local MCP bridge). Declarative only in Prompt 02 — these are the
# server/tool/resource/prompt/receipt/denial/permission-audit/gate contracts plus the
# validation matrix; no server or runtime dispatch consumes them yet. The Claude Desktop
# config-preview JSON Schema ships alongside as a plain resource (used from Prompt 09), not
# registered here.
PHASE_08D_CONTRACT_FILES: dict[str, str] = {
    "server_config_contract": "phase_08d_mcp_server_config_contract.json",
    "allowed_tools_contract": "phase_08d_mcp_allowed_tools_contract.json",
    "denied_tools_contract": "phase_08d_mcp_denied_tools_contract.json",
    "tool_call_receipt_contract": "phase_08d_mcp_tool_call_receipt_contract.json",
    "denial_receipt_contract": "phase_08d_mcp_denial_receipt_contract.json",
    "resources_contract": "phase_08d_mcp_resources_contract.json",
    "prompts_contract": "phase_08d_mcp_prompts_contract.json",
    "permission_audit_contract": "phase_08d_mcp_permission_audit_contract.json",
    "data_quality_gates_contract": "phase_08d_data_quality_gates_contract.json",
    "validation_matrix": "phase_08d_validation_matrix.json",
}

def load_phase_08d_contract(name: str) -> dict[str, Any]:
    """Load a single Phase 08D contract by logical name."""
    if name not in PHASE_08D_CONTRACT_FILES:
        raise KeyError(f"unknown phase 08D contract: {name!r}")
    return _load_json_resource(PHASE_08D_CONTRACT_FILES[name])

def load_all_phase_08d_contracts() -> dict[str, dict[str, Any]]:
    """Load every registered Phase 08D contract (logical name -> parsed dict)."""
    return {name: load_phase_08d_contract(name) for name in PHASE_08D_CONTRACT_FILES}

# Phase 09 Prompt 13 — optional LlamaIndex retrieval config contract.
PHASE_09_CONTRACT_FILES: dict[str, str] = {
    "llamaindex_config_contract": "phase_09_llamaindex_config_contract.json",
    "embedding_vector_policy_contract": "phase_09_embedding_vector_policy_contract.json",
    "approved_source_manifest_contract": "phase_09_approved_source_manifest_contract.json",
    "vector_index_apply_contract": "phase_09_vector_index_apply_contract.json",
    "hybrid_retrieval_contract": "phase_09_hybrid_retrieval_contract.json",
    "metadata_filter_contract": "phase_09_metadata_filter_contract.json",
    "research_packet_integration_contract": "phase_09_research_packet_integration_contract.json",
    "output_evaluation_integration_contract": "phase_09_output_evaluation_integration_contract.json",
    "retrieval_eval_set_contract": "phase_09_retrieval_eval_set_contract.json",
    "retrieval_benchmark_contract": "phase_09_retrieval_benchmark_contract.json",
    "project_retrieval_benchmark_contract": "phase_09_project_retrieval_benchmark_contract.json",
    "context_budget_optimization_contract": "phase_09_context_budget_optimization_contract.json",
    "unsupported_claim_checks_contract": "phase_09_unsupported_claim_checks_contract.json",
    "hallucination_risk_checks_contract": "phase_09_hallucination_risk_checks_contract.json",
    "memory_quality_review_contract": "phase_09_memory_quality_review_contract.json",
    "review_burden_policy_contract": "phase_09_review_burden_policy_contract.json",
}

def load_phase_09_contract(name: str) -> dict[str, Any]:
    """Load a single Phase 09 contract by logical name."""
    if name not in PHASE_09_CONTRACT_FILES:
        raise KeyError(f"unknown phase 09 contract: {name!r}")
    return _load_json_resource(PHASE_09_CONTRACT_FILES[name])

def load_all_phase_09_contracts() -> dict[str, dict[str, Any]]:
    """Load every registered Phase 09 contract (logical name -> parsed dict)."""
    return {name: load_phase_09_contract(name) for name in PHASE_09_CONTRACT_FILES}
