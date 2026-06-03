"""Phase 08B automation / observability policy (Prompt 02).

Loads the deterministic Phase 08B automation policy seed (health-check posture, retry/backoff,
weekend behavior, local-only alerting, structured reason codes) and validates it against the
``automation_policy_contract``. Read-only; no model; no external delivery. Declarative substrate
only — the execution (running checks/retries, real launchd install) is owned by a later 08B prompt.
Mirrors ``daily_brief/policy.py``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from .contracts import load_phase_08b_contract

_SEED_RELATIVE = Path("resources") / "config" / "phase_08b_automation_policy.seed.yaml"
AUTOMATION_POLICY_SEED_ENV_VAR = "HB_SECOND_BRAIN_08B_AUTOMATION_POLICY"

# Prompt 01 addendum — dedicated executor policy seeds (details for the deferred automation executor;
# high-level refs live in the main automation policy seed; reason codes are in the shared vocab).
_EXECUTOR_POLICY_RELATIVE = Path("resources") / "config" / "phase_08b_automation_executor_policy.seed.yaml"
EXECUTOR_POLICY_SEED_ENV_VAR = "HB_SECOND_BRAIN_08B_EXECUTOR_POLICY"

_STAGE_REGISTRY_RELATIVE = Path("resources") / "config" / "phase_08b_executor_stage_registry.seed.yaml"
STAGE_REGISTRY_SEED_ENV_VAR = "HB_SECOND_BRAIN_08B_STAGE_REGISTRY"

_RETRY_BACKOFF_RELATIVE = Path("resources") / "config" / "phase_08b_retry_backoff_policy.seed.yaml"
RETRY_BACKOFF_SEED_ENV_VAR = "HB_SECOND_BRAIN_08B_RETRY_BACKOFF"

_WEEKEND_CATCHUP_RELATIVE = Path("resources") / "config" / "phase_08b_weekend_catchup_policy.seed.yaml"
WEEKEND_CATCHUP_SEED_ENV_VAR = "HB_SECOND_BRAIN_08B_WEEKEND_CATCHUP"


class AutomationPolicyError(RuntimeError):
    """Raised when the Phase 08B automation policy seed cannot be loaded."""


def load_phase_08b_automation_policy_seed() -> dict[str, Any]:
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(AUTOMATION_POLICY_SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise AutomationPolicyError(f"automation policy seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise AutomationPolicyError(f"{candidate} must contain a mapping at top level")
    return data


def _load_yaml(relative: Path, env_var: str) -> dict[str, Any]:
    """Internal loader (duplicated pattern for the 4 Prompt-01 executor seeds; keeps changes minimal)."""
    candidate = PathPolicy().resolve_repo_root() / relative
    env_value = os.environ.get(env_var)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise AutomationPolicyError(f"seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise AutomationPolicyError(f"{candidate} must contain a mapping at top level")
    return data


def load_phase_08b_automation_executor_policy_seed() -> dict[str, Any]:
    return _load_yaml(_EXECUTOR_POLICY_RELATIVE, EXECUTOR_POLICY_SEED_ENV_VAR)


def load_phase_08b_executor_stage_registry_seed() -> dict[str, Any]:
    return _load_yaml(_STAGE_REGISTRY_RELATIVE, STAGE_REGISTRY_SEED_ENV_VAR)


def load_phase_08b_retry_backoff_policy_seed() -> dict[str, Any]:
    return _load_yaml(_RETRY_BACKOFF_RELATIVE, RETRY_BACKOFF_SEED_ENV_VAR)


def load_phase_08b_weekend_catchup_policy_seed() -> dict[str, Any]:
    return _load_yaml(_WEEKEND_CATCHUP_RELATIVE, WEEKEND_CATCHUP_SEED_ENV_VAR)


def validate_phase_08b_automation_policy() -> dict[str, Any]:
    """Validate the automation policy seed against its contract. Read-only; deterministic."""
    contract = load_phase_08b_contract("automation_policy_contract")
    seed = load_phase_08b_automation_policy_seed()
    violations: list[dict[str, str]] = []

    for section in contract.get("required_sections", []):
        if section not in seed:
            violations.append({"code": f"seed_missing_section:{section}"})

    # Alerting must be local-only — external channels are never permitted.
    channel = seed.get("alerting", {}).get("channel")
    if channel not in contract.get("alerting_channels_allowed", []):
        violations.append({"code": f"alerting_channel_not_allowed:{channel}"})

    # The seed's reason codes must be a subset of the contract-declared vocabulary.
    allowed = set(contract.get("reason_codes", []))
    for code in seed.get("reason_codes", []):
        if code not in allowed:
            violations.append({"code": f"reason_code_not_in_contract:{code}"})

    return {
        "valid": not violations,
        "contract_version": contract.get("version", "unknown"),
        "seed_version": seed.get("version", "unknown"),
        "reason_codes": list(seed.get("reason_codes", [])),
        "violations": violations,
    }
