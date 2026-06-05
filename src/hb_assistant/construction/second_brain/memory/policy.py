"""Phase 08A memory + operator-preference policy (Prompt 10).

Deterministic tier classification for memory candidates and operator preferences, plus
the hard rule that **accepted preferences can never override safety policy / review-tier
routing**. Sensitive/high-impact material routes to Tier 3 (mandatory review, never
auto-accepted). The registered ``review_tier_contract`` is authoritative for the
sensitive/high-impact category set; the seeds add posture flags.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from ..contracts import load_phase_08a_contract

_MEMORY_SEED_RELATIVE = Path("resources") / "config" / "phase_08a_memory_policy.seed.yaml"
_PREF_SEED_RELATIVE = (
    Path("resources") / "config" / "phase_08a_operator_preference_policy.seed.yaml"
)
MEMORY_POLICY_ENV_VAR = "HB_SECOND_BRAIN_MEMORY_POLICY"
PREFERENCE_POLICY_ENV_VAR = "HB_SECOND_BRAIN_PREFERENCE_POLICY"

# Preference keys the operator-preference layer may apply (presentation only).
_ALLOWED_PRESENTATION_KEYS: frozenset[str] = frozenset(
    {
        "output_structure",
        "detail_level",
        "terminology",
        "emphasis",
        "warning_style",
        "executive_summary_style",
    }
)

# Substrings in a preference key/value that would touch safety / routing — never applied.
_SAFETY_AFFECTING_TOKENS: tuple[str, ...] = (
    "tier",
    "review",
    "safety",
    "suppress",
    "disable",
    "bypass",
    "override",
    "writeback",
    "raw_content",
    "guardrail",
    "high_impact",
)


class MemoryPolicyError(RuntimeError):
    """Raised when a memory / preference policy seed cannot be loaded."""


def _load_yaml(relative: Path, env_var: str) -> dict[str, Any]:
    candidate = PathPolicy().resolve_repo_root() / relative
    env_value = os.environ.get(env_var)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise MemoryPolicyError(f"policy seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise MemoryPolicyError(f"{candidate} must contain a mapping at top level")
    return data


def load_memory_policy_seed() -> dict[str, Any]:
    return _load_yaml(_MEMORY_SEED_RELATIVE, MEMORY_POLICY_ENV_VAR)


def load_operator_preference_policy_seed() -> dict[str, Any]:
    return _load_yaml(_PREF_SEED_RELATIVE, PREFERENCE_POLICY_ENV_VAR)


def sensitive_high_impact_categories() -> frozenset[str]:
    """The authoritative sensitive/high-impact set (review_tier_contract + memory seed)."""
    contract = load_phase_08a_contract("review_tier_contract")
    mandatory = set(contract.get("mandatory_review_for", []))
    seed = load_memory_policy_seed()
    return frozenset(
        mandatory
        | set(seed.get("sensitive_high_impact_categories", []))
        | set(seed.get("tier_3_always", []))
    )


def classify_memory_tier(
    *,
    sensitivity_category: str | None,
    confidence_class: str,
    source_linked: bool,
    conflict: bool = False,
    model_only: bool = False,
) -> tuple[int, str]:
    """Deterministically classify a memory candidate into a review tier + reason code.

    Sensitive/high-impact, model-only, conflicting, or unsupported (not source-linked)
    material is always Tier 3 (mandatory review; never auto-accepted).
    """
    sensitive = sensitivity_category is not None and (
        sensitivity_category in sensitive_high_impact_categories()
    )
    if sensitive:
        return 3, "T3_SENSITIVE_HIGH_IMPACT"
    if not source_linked:
        return 3, "T3_UNSUPPORTED"
    if model_only:
        return 3, "T3_MODEL_ONLY"
    if conflict:
        return 3, "T3_CONFLICT_DETECTED"
    conf = (confidence_class or "").lower()
    if conf == "high":
        return 1, "T1_DETERMINISTIC_SOURCE_BACKED"
    if conf == "medium":
        return 2, "T2_STRONG_HEURISTIC"
    return 3, "T3_LOW_CONFIDENCE"


def classify_preference(*, preference_type: str, sensitive: bool = False) -> tuple[int, str, str]:
    """Classify an operator preference -> (review_tier, review_tier_reason_code, review_status).

    Preferences are never auto-accepted (always start pending_review). Sensitive
    preferences (personnel/legal/financial/safety) route to Tier 3.
    """
    seed = load_operator_preference_policy_seed()
    sensitive_types = set(seed.get("sensitive_preference_types", []))
    if sensitive or preference_type in sensitive_types:
        return 3, "T3_SENSITIVE_HIGH_IMPACT", "pending_review"
    return 2, "T2_STRONG_HEURISTIC", "pending_review"


def preference_key_is_safety_affecting(preference_key: str, value: str | None = None) -> bool:
    """A preference is safety-affecting if its key isn't an allowed presentation key
    or if the key/value mentions tier/review/safety/guardrail tokens."""
    blob = f"{preference_key} {value or ''}".lower()
    if any(tok in blob for tok in _SAFETY_AFFECTING_TOKENS):
        return True
    return preference_key not in _ALLOWED_PRESENTATION_KEYS


def apply_operator_preferences(
    preferences: list[dict[str, Any]],
) -> tuple[dict[str, str], list[str]]:
    """Apply ONLY accepted, presentation-only preferences.

    Returns (applied_hints, dropped_keys). Any safety-affecting or non-allowlisted
    preference is dropped — preferences can never override safety policy / review-tier
    routing / guardrails.
    """
    applied: dict[str, str] = {}
    dropped: list[str] = []
    for pref in preferences:
        key = str(pref.get("preference_key", ""))
        value = pref.get("preference_value_redacted")
        if pref.get("review_status") != "accepted":
            dropped.append(f"{key}:not_accepted")
            continue
        if preference_key_is_safety_affecting(key, value):
            dropped.append(f"{key}:safety_affecting_ignored")
            continue
        applied[key] = str(value) if value is not None else ""
    return applied, dropped


def validate_memory_policy() -> dict[str, Any]:
    """Validate the seeds + that the memory/preference models cover their contracts."""
    from .models import MemoryCandidate, OperatorPreference

    violations: list[dict[str, str]] = []
    memory_seed = load_memory_policy_seed()
    pref_seed = load_operator_preference_policy_seed()

    for flag in ("origin_required", "source_refs_required", "review_tier_required"):
        if memory_seed.get(flag) is not True:
            violations.append({"code": f"memory_seed_flag_not_true:{flag}"})
    if not memory_seed.get("tier_3_always"):
        violations.append({"code": "memory_seed_missing_tier_3_always"})

    # Preferences must declare what they can never override (incl. safety).
    never = set(pref_seed.get("never_overrides", []))
    if "safety_policy" not in never or "review_tier_routing" not in never:
        violations.append({"code": "preference_seed_missing_safety_never_override"})

    candidate_fields = set(MemoryCandidate.model_fields)
    if "origin_id" not in candidate_fields or "source_refs" not in candidate_fields:
        violations.append({"code": "candidate_model_missing_origin_or_source_refs"})
    if "review_status" not in set(OperatorPreference.model_fields):
        violations.append({"code": "preference_model_missing_review_status"})

    return {
        "valid": not violations,
        "memory_policy_version": memory_seed.get("version", "unknown"),
        "preference_policy_version": pref_seed.get("version", "unknown"),
        "sensitive_high_impact_count": len(sensitive_high_impact_categories()),
        "violations": violations,
    }
