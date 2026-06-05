"""Phase 08A SQLite query-tool allowlist + policy (Prompt 06).

Defines the allowlisted query-tool *names*, maps each to an approved local
read-model source family (or ``None`` when no read-model is built yet), and
validates the seed + contract posture (no arbitrary/mutation SQL, source refs +
review tier mandatory). The model never generates SQL; only these names dispatch.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from ..contracts import load_phase_08a_contract

# Allowlisted query-tool names (the approved surface; mirrors the seed + contract).
ALLOWLISTED_QUERY_TOOLS: tuple[str, ...] = (
    "project_context",
    "source_coverage",
    "relationship_candidates",
    "accepted_relationships",
    "source_evidence_trails",
    "meeting_prep_briefs",
    "issue_history",
    "risk_digest",
    "aging_exposure",
    "review_queue_status",
    "memory_items",
    "research_packet_status",
    "evaluation_status",
)

# Tool -> approved read-model source family. ``None`` => composite/orchestrator
# territory (Prompt 07/08) with no single read-model; resolves to ``no_read_model``.
QUERY_TOOL_FAMILY_MAP: dict[str, str | None] = {
    "project_context": None,
    "source_coverage": None,
    "relationship_candidates": "cross_source_relationships",
    "accepted_relationships": "cross_source_relationships",
    "source_evidence_trails": "phase_07d_source_evidence_trails",
    "meeting_prep_briefs": "meeting_prep_brief_sections",  # reader-backed (Phase 09 coverage expansion)
    "issue_history": "project_issue_history_items",
    "risk_digest": "project_risk_digest_items",
    "aging_exposure": "aging_exposure_report_items",
    "review_queue_status": None,
    "memory_items": "accepted_long_term_memory",
    "research_packet_status": None,  # Prompt 07
    "evaluation_status": None,  # Prompt 07/08
}

# V25 relationship runtime labels split for the two relationship tools.
_ACCEPTED_RELATIONSHIP_STATES: frozenset[str] = frozenset(
    {"authoritative_deterministic", "accepted_human_promoted"}
)
_CANDIDATE_RELATIONSHIP_STATES: frozenset[str] = frozenset(
    {
        "suggested_strong",
        "suggested_weak",
        "model_proposed_review_required",
        "sensitive_review_required",
        "stale_or_unresolved",
    }
)

_SEED_RELATIVE = Path("resources") / "config" / "phase_08a_sqlite_query_tool_allowlist.seed.yaml"
QUERY_TOOL_SEED_ENV_VAR = "HB_SECOND_BRAIN_QUERY_TOOLS"


class QueryToolError(RuntimeError):
    """Raised when a non-allowlisted tool is requested or the seed cannot load."""


def relationship_states_for(tool_name: str) -> frozenset[str]:
    """Return the allowed V25 relationship states for a relationship tool."""
    if tool_name == "accepted_relationships":
        return _ACCEPTED_RELATIONSHIP_STATES
    return _CANDIDATE_RELATIONSHIP_STATES


def load_query_tool_allowlist_seed() -> dict[str, Any]:
    """Load the query-tool allowlist seed (repo seed, env override)."""
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(QUERY_TOOL_SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise QueryToolError(f"query-tool seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise QueryToolError(f"{candidate} must contain a mapping at top level")
    return data


def validate_query_tool_policy() -> dict[str, Any]:
    """Validate the query-tool contract + seed against the allowlist + guardrails."""
    contract = load_phase_08a_contract("sqlite_query_tool")
    seed = load_query_tool_allowlist_seed()
    violations: list[dict[str, str]] = []

    allowlist = set(ALLOWLISTED_QUERY_TOOLS)
    if set(seed.get("allowlisted_tools", [])) != allowlist:
        violations.append({"code": "seed_allowlist_mismatch"})
    if set(contract.get("allowlisted_tools", [])) != allowlist:
        violations.append({"code": "contract_allowlist_mismatch"})

    # No arbitrary / mutation SQL, in either surface.
    for surface, blob in (("seed", seed), ("contract", contract)):
        if blob.get("arbitrary_sql_allowed", True) is not False:
            violations.append({"code": f"{surface}_arbitrary_sql_allowed"})
        if blob.get("mutation_sql_allowed", True) is not False:
            violations.append({"code": f"{surface}_mutation_sql_allowed"})

    # Source refs + review tier mandatory (seed flags).
    if seed.get("source_refs_required") is not True:
        violations.append({"code": "seed_source_refs_not_required"})
    if seed.get("review_tier_required") is not True:
        violations.append({"code": "seed_review_tier_not_required"})

    # Contract must carry the forbidden raw-field denylist.
    if not contract.get("forbidden_fields"):
        violations.append({"code": "contract_missing_forbidden_fields"})

    backed = sorted(t for t, fam in QUERY_TOOL_FAMILY_MAP.items() if fam is not None)
    return {
        "valid": not violations,
        "contract_version": contract.get("version", "unknown"),
        "seed_version": seed.get("version", "unknown"),
        "allowlisted_count": len(ALLOWLISTED_QUERY_TOOLS),
        "backed_tools": backed,
        "violations": violations,
    }
