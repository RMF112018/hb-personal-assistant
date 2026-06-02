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
}


def _load_json_resource(filename: str) -> dict[str, Any]:
    """Load a packaged json resource. importlib -> filesystem -> empty dict."""
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(_CONTRACT_PKG) / filename).read_text(
                encoding="utf-8"
            )
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
