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
