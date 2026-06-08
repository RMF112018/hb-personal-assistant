"""Phase 08A research-packet policy + deterministic context-quality scoring (Prompt 07).

Loads the research-packet policy seed (quality thresholds + degradation mapping) and
scores retrieved context into a context-quality class + degradation recommendation.
Deterministic; read-only; no model. The repo ``research_packet_contract`` (3-value
degradation vocabulary, compact required_fields) is authoritative over the package's
fuller proposed schema.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from ..contracts import load_phase_08a_contract
from .models import ResearchPacket

# Packet types the model recognizes (model-level; not a persisted V26 column).
PACKET_TYPES: tuple[str, ...] = (
    "daily_brief",
    "interactive_query",
    "chat_turn",
    "memory_extraction",
    "targeted_research",
    # Phase 10A Prompt 09: raw-capable packet types (config-gated downstream exposure via MCP/Obsidian when policy allows)
    "raw_email_context",
    "raw_calendar_context",
    "raw_daily_brief_context",
    # Phase 10A: bounded, purposeful action/triage packets (one coherent unit per packet)
    "email_thread_action_packet",
    "calendar_event_action_packet",
    "related_context_action_packet",
    "triage_batch_packet",
    "daily_brief_packet",
)

# Packet types whose synthesis requires a research packet first. ``high_impact_query``
# is an alias of the complex interactive-query path (see the seed's required_for).
_REQUIRED_FOR: frozenset[str] = frozenset(
    {"daily_brief", "interactive_query", "high_impact_query", "memory_extraction"}
)

# Map the actionable 5-value recommendation -> the contract's 3-value degradation_mode.
_RECOMMENDATION_TO_PACKET_MODE: dict[str, str] = {
    "none": "none",
    "narrow_claims": "graceful_degraded",
    "advisory_only": "graceful_degraded",
    "ask_for_targeted_research": "graceful_degraded",
    "blocked": "blocked",
}

_SEED_RELATIVE = Path("resources") / "config" / "phase_08a_research_packet_policy.seed.yaml"
RESEARCH_PACKET_SEED_ENV_VAR = "HB_SECOND_BRAIN_RESEARCH_PACKET_POLICY"


class ResearchPacketPolicyError(RuntimeError):
    """Raised when the research-packet policy seed cannot be loaded."""


def requires_research_packet(packet_type: str) -> bool:
    """Whether synthesis for this packet type must be preceded by a research packet."""
    if packet_type.startswith("raw_"):
        # raw_* packets (P09) are self-contained raw context sources; they do not require the standard redacted research packet first.
        return False
    return packet_type in _REQUIRED_FOR


def load_research_packet_policy_seed() -> dict[str, Any]:
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(RESEARCH_PACKET_SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise ResearchPacketPolicyError(f"research-packet policy seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ResearchPacketPolicyError(f"{candidate} must contain a mapping at top level")
    return data


def score_context_quality(
    *,
    total_items: int,
    tier3_count: int,
    stale_unknown_count: int,
    conflict_count: int,
    source_ref_completeness: float,
    source_coverage: float,
) -> dict[str, Any]:
    """Deterministically score retrieved context into a quality class + degradation.

    Precedence (most severe first): no items / missing source refs -> blocked;
    conflicts -> ask_for_targeted_research; high tier-3 density -> advisory_only;
    high stale density or low coverage -> narrow_claims; else none. Insufficient
    context degrades or blocks — it never produces an "ok to overstate" result.
    """
    seed = load_research_packet_policy_seed()
    thr = seed.get("quality_thresholds", {})
    max_t3 = float(thr.get("max_tier_3_density_for_standard_synthesis", 0.35))
    max_stale = float(thr.get("max_stale_unknown_density_for_standard_synthesis", 0.30))
    min_ref = float(thr.get("min_source_reference_completeness", 0.95))
    min_cov = float(thr.get("min_source_coverage", 0.5))

    tier3_density = (tier3_count / total_items) if total_items else 1.0
    stale_density = (stale_unknown_count / total_items) if total_items else 1.0
    warnings: list[str] = []

    if total_items == 0:
        recommendation = "blocked"
        warnings.append("no_context_retrieved")
    elif source_ref_completeness < min_ref:
        recommendation = "blocked"
        warnings.append(
            f"source_ref_completeness_below_min:{source_ref_completeness:.2f}<{min_ref}"
        )
    elif conflict_count > 0:
        recommendation = "ask_for_targeted_research"
        warnings.append(f"conflicting_sources:{conflict_count}")
    elif tier3_density > max_t3:
        recommendation = "advisory_only"
        warnings.append(f"tier_3_density_exceeds_threshold:{tier3_density:.2f}>{max_t3}")
    elif stale_density > max_stale or source_coverage < min_cov:
        recommendation = "narrow_claims"
        if stale_density > max_stale:
            warnings.append(
                f"stale_unknown_density_exceeds_threshold:{stale_density:.2f}>{max_stale}"
            )
        if source_coverage < min_cov:
            warnings.append(f"source_coverage_below_min:{source_coverage:.2f}<{min_cov}")
    else:
        recommendation = "none"

    degradation_mode = _RECOMMENDATION_TO_PACKET_MODE[recommendation]
    if degradation_mode == "blocked":
        context_quality_class = "insufficient"
    elif degradation_mode == "none":
        context_quality_class = "sufficient"
    else:
        context_quality_class = "partial"
    confidence_class = {"sufficient": "high", "partial": "medium", "insufficient": "low"}[
        context_quality_class
    ]

    return {
        "context_quality_class": context_quality_class,
        "degradation_mode": degradation_mode,
        "degradation_recommendation": recommendation,
        "confidence_class": confidence_class,
        "policy_warnings": warnings,
    }


def validate_research_packet_policy() -> dict[str, Any]:
    """Validate the packet model covers the contract required_fields + seed thresholds."""
    contract = load_phase_08a_contract("research_packet_contract")
    seed = load_research_packet_policy_seed()
    violations: list[dict[str, str]] = []

    model_fields = set(ResearchPacket.model_fields)
    for field in contract.get("required_fields", []):
        if field not in model_fields:
            violations.append({"code": f"model_missing_contract_field:{field}"})

    thr = seed.get("quality_thresholds", {})
    for key in (
        "max_tier_3_density_for_standard_synthesis",
        "max_stale_unknown_density_for_standard_synthesis",
        "min_source_reference_completeness",
        "min_source_coverage",
    ):
        if key not in thr:
            violations.append({"code": f"seed_missing_threshold:{key}"})

    contract_modes = set(contract.get("degradation_modes", []))
    packet_modes = set(_RECOMMENDATION_TO_PACKET_MODE.values())
    if not packet_modes <= contract_modes:
        violations.append({"code": "degradation_mode_not_in_contract"})

    return {
        "valid": not violations,
        "contract_version": contract.get("version", "unknown"),
        "seed_version": seed.get("version", "unknown"),
        "violations": violations,
    }
