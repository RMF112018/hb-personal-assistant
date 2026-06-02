"""Phase 08A daily-brief + review-triage policy (Prompt 11).

Loads the deterministic daily-brief policy seed (assembly posture, triage prioritization
order, card classification thresholds) and validates the daily-brief contract against the
card/section vocabulary the builder emits. Read-only; no model. The repo
``daily_brief_contract`` (required_fields, brief_sections, card_kinds) is authoritative.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from ..contracts import load_phase_08a_contract

# Tier -> review_tier_reason_code (mirrors the broker/packet reason vocabulary).
TIER_REASON_CODES: dict[int, str] = {
    1: "T1_SOURCE_BACKED",
    2: "T2_REVIEW_RECOMMENDED",
    3: "T3_MANDATORY_REVIEW",
}

_SEED_RELATIVE = Path("resources") / "config" / "phase_08a_daily_brief_policy.seed.yaml"
DAILY_BRIEF_SEED_ENV_VAR = "HB_SECOND_BRAIN_DAILY_BRIEF_POLICY"


class DailyBriefPolicyError(RuntimeError):
    """Raised when the daily-brief policy seed cannot be loaded."""


def load_daily_brief_policy_seed() -> dict[str, Any]:
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(DAILY_BRIEF_SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise DailyBriefPolicyError(f"daily-brief policy seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise DailyBriefPolicyError(f"{candidate} must contain a mapping at top level")
    return data


def reason_code_for_tier(tier: int) -> str:
    """Deterministic review_tier_reason_code for a review tier (defaults Tier 3)."""
    return TIER_REASON_CODES.get(tier, "T3_MANDATORY_REVIEW")


def validate_daily_brief_policy() -> dict[str, Any]:
    """Validate the daily-brief contract + seed are consistent with builder output."""
    contract = load_phase_08a_contract("daily_brief_contract")
    seed = load_daily_brief_policy_seed()
    violations: list[dict[str, str]] = []

    from .models import HANDOFF_SECTIONS

    for section in HANDOFF_SECTIONS:
        if section not in contract.get("brief_sections", []):
            violations.append({"code": f"contract_missing_brief_section:{section}"})

    triage = seed.get("triage_prioritization", {})
    if not triage.get("order"):
        violations.append({"code": "seed_missing_triage_order"})

    return {
        "valid": not violations,
        "contract_version": contract.get("version", "unknown"),
        "seed_version": seed.get("version", "unknown"),
        "violations": violations,
    }
