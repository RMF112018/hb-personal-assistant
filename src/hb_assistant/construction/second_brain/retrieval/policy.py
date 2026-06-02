"""Phase 08A retrieval policy + context budget (Synthesized Prompt 04).

Loads the retrieval-policy and context-budget contracts/seeds, enforces the
allowlist/deny posture, derives V25 relationship runtime labels WITHOUT rewriting
V25 records, and applies the deterministic context budget. Read-only; no external
access, no embeddings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy

from ..contracts import load_phase_08a_contract
from .models import RetrievalItem

# Allowlisted source families the broker may read (read-model-backed + relationships
# per Prompt 04 scope). Disjoint from the excluded raw families by construction.
ALLOWLISTED_SOURCE_FAMILIES: tuple[str, ...] = (
    "phase_07d_source_evidence_trails",
    "meeting_prep_brief_sections",
    "project_issue_history_items",
    "project_risk_digest_items",
    "aging_exposure_report_items",
    "review_controlled_correspondence_context",
    "approved_obsidian_generated_outputs",
    "accepted_long_term_memory",
    "cross_source_relationships",
)

# Raw families that may never be retrieved (mirrors retrieval_policy_contract excluded).
EXCLUDED_FAMILIES: frozenset[str] = frozenset(
    {
        "raw_email_body",
        "raw_email_bodies",
        "raw_document_text",
        "raw_calendar_payload",
        "raw_calendar_payloads",
        "raw_prompt",
        "raw_prompts",
        "raw_response",
        "raw_model_responses",
        "signed_url",
        "signed_urls",
        "download_url",
        "download_urls",
        "secret",
        "secrets",
    }
)

_RETRIEVAL_SEED_RELATIVE = Path("resources") / "config" / "phase_08a_retrieval_policy.seed.yaml"
_BUDGET_SEED_RELATIVE = Path("resources") / "config" / "phase_08a_context_budget.seed.yaml"
RETRIEVAL_SEED_ENV_VAR = "HB_SECOND_BRAIN_RETRIEVAL_POLICY"
BUDGET_SEED_ENV_VAR = "HB_SECOND_BRAIN_CONTEXT_BUDGET"

# V25 relationship runtime labels (derived, never written back).
_RELATIONSHIP_TIER: dict[str, int] = {
    "authoritative_deterministic": 1,
    "accepted_human_promoted": 1,
    "suggested_strong": 2,
    "suggested_weak": 2,
    "model_proposed_review_required": 3,
    "sensitive_review_required": 3,
    "stale_or_unresolved": 3,
    "rejected_excluded": 3,
}


class RetrievalPolicyError(RuntimeError):
    """Raised when a retrieval seed cannot be loaded."""


class ContextBudget(BaseModel):
    """Deterministic context budget (loaded from the seed)."""

    version: str
    max_context_chars: int
    max_item_chars: int
    tier_priority: list[str]
    deterministic_truncation: bool
    truncation_order: list[str] = []
    degradation_behavior: str = "graceful_degraded"
    degradation_modes: list[str] = []

    model_config = {"extra": "forbid"}


def _load_yaml(relative: Path, env_var: str) -> dict[str, Any]:
    candidate = PathPolicy().resolve_repo_root() / relative
    env_value = os.environ.get(env_var)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise RetrievalPolicyError(f"seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise RetrievalPolicyError(f"{candidate} must contain a mapping at top level")
    return data


def load_retrieval_policy_seed() -> dict[str, Any]:
    return _load_yaml(_RETRIEVAL_SEED_RELATIVE, RETRIEVAL_SEED_ENV_VAR)


def load_context_budget() -> ContextBudget:
    return ContextBudget.model_validate(_load_yaml(_BUDGET_SEED_RELATIVE, BUDGET_SEED_ENV_VAR))


def validate_retrieval_policy() -> dict[str, Any]:
    """Validate the retrieval policy contract + seed against the broker allowlist."""
    contract = load_phase_08a_contract("retrieval_policy_contract")
    budget_contract = load_phase_08a_contract("context_budget_contract")
    seed = load_retrieval_policy_seed()
    budget = load_context_budget()

    violations: list[dict[str, str]] = []

    approved = list(seed.get("approved_sources", []))
    excluded = set(seed.get("excluded_sources", [])) | set(contract.get("excluded", []))

    # No allowlisted family may be an excluded raw family.
    for fam in ALLOWLISTED_SOURCE_FAMILIES:
        if fam in EXCLUDED_FAMILIES or fam in excluded:
            violations.append({"family": fam, "code": "allowlisted_family_excluded"})

    # Every approved read-model family must be covered by the broker allowlist.
    for fam in approved:
        if fam not in ALLOWLISTED_SOURCE_FAMILIES:
            violations.append({"family": fam, "code": "approved_family_not_in_allowlist"})

    # Budget seed must satisfy the budget contract's required fields.
    for field in budget_contract.get("required_fields", []):
        if not hasattr(budget, field):
            violations.append({"family": "*", "code": f"budget_missing_field:{field}"})

    return {
        "valid": not violations,
        "policy_version": contract.get("version", "unknown"),
        "budget_version": budget.version,
        "approved_count": len(approved),
        "allowlisted_count": len(ALLOWLISTED_SOURCE_FAMILIES),
        "excluded_count": len(excluded),
        "violations": violations,
    }


def derive_relationship_state(record: dict[str, Any]) -> str:
    """Derive a V25 relationship runtime label (read-only; no writeback).

    Deterministic precedence over the existing V25 fields — original rows are never
    modified.
    """
    promotion = (record.get("promotion_status") or "").lower()
    if promotion in {"rejected", "excluded"}:
        return "rejected_excluded"
    if promotion in {"promoted", "accepted"} or record.get("promoted_by"):
        return "accepted_human_promoted"
    if record.get("deterministic"):
        return "authoritative_deterministic"
    if record.get("sensitive_high_impact"):
        return "sensitive_review_required"
    if record.get("model_proposed"):
        return "model_proposed_review_required"
    if record.get("stale_unknown") or promotion in {"stale", "unresolved"}:
        return "stale_or_unresolved"
    if (record.get("confidence_class") or "").lower() == "high":
        return "suggested_strong"
    return "suggested_weak"


def relationship_state_tier(state: str) -> int:
    return _RELATIONSHIP_TIER.get(state, 3)


def apply_context_budget(
    items: list[RetrievalItem], budget: ContextBudget
) -> tuple[list[RetrievalItem], int, bool, str]:
    """Deterministically bound items by tier -> recency -> source quality.

    Returns (kept_items, context_char_count, truncated, degradation_mode).
    """
    confidence_rank = {"high": 0, "medium": 1, "low": 2, "unknown": 3}

    # Staged stable sorts (lowest priority first): tier 1 first, then newest first,
    # then highest confidence, with source_ref as the deterministic tiebreak.
    ordered = sorted(items, key=lambda it: it.source_ref)
    ordered = sorted(ordered, key=lambda it: confidence_rank.get(it.confidence_class.lower(), 3))
    ordered = sorted(ordered, key=lambda it: it.recency, reverse=True)
    ordered = sorted(ordered, key=lambda it: it.review_tier)

    kept: list[RetrievalItem] = []
    char_count = 0
    truncated = False
    for it in ordered:
        excerpt = it.content_excerpt_redacted[: budget.max_item_chars]
        if it.content_excerpt_redacted != excerpt:
            it = it.model_copy(update={"content_excerpt_redacted": excerpt})
        if char_count + len(excerpt) > budget.max_context_chars:
            truncated = True
            break
        kept.append(it)
        char_count += len(excerpt)

    if not kept:
        degradation = "blocked"
    elif truncated:
        degradation = "narrow_claims"
    else:
        degradation = "none"
    return kept, char_count, truncated, degradation
