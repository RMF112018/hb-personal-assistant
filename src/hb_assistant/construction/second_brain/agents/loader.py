"""Phase 08A agent registry + model-profiles seed loaders (Prompt 02 Addendum).

Mirrors ``construction/policy/loader.py``: YAML seed resolved relative to the
repo root, replacement-semantics overrides (seed -> repo override -> explicit ->
env), Pydantic validation for the registry. Read-only; no external access.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from .models import AgentRegistry

REGISTRY_SEED_RELATIVE_PATH = Path("resources") / "config" / "phase_08a_agent_registry.seed.yaml"
REGISTRY_REPO_OVERRIDE_RELATIVE_PATH = Path("config") / "phase_08a_agent_registry.yml"
REGISTRY_ENV_VAR = "HB_SECOND_BRAIN_AGENT_REGISTRY"

MODEL_PROFILES_SEED_RELATIVE_PATH = (
    Path("resources") / "config" / "phase_08a_model_profiles.seed.yaml"
)
MODEL_PROFILES_REPO_OVERRIDE_RELATIVE_PATH = Path("config") / "phase_08a_model_profiles.yml"
MODEL_PROFILES_ENV_VAR = "HB_SECOND_BRAIN_MODEL_PROFILES"


class AgentRegistryError(RuntimeError):
    """Raised when the agent registry seed cannot be loaded."""


class ModelProfilesError(RuntimeError):
    """Raised when the model-profiles seed cannot be loaded."""


def _load_yaml(path: Path, *, error: type[RuntimeError]) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise error(f"{path} must contain a mapping at top level")
    return data


def _resolve(relative: Path) -> Path:
    return PathPolicy().resolve_repo_root() / relative


def load_agent_registry(override_path: Path | str | None = None) -> AgentRegistry:
    """Load and validate the Phase 08A agent registry (replacement semantics)."""
    seed_path = _resolve(REGISTRY_SEED_RELATIVE_PATH)
    if not seed_path.exists():
        raise AgentRegistryError(
            f"Seed agent registry not found at {seed_path}. "
            "Phase 08A agent runtime cannot start without the seeded registry."
        )

    data: dict[str, Any] = _load_yaml(seed_path, error=AgentRegistryError)

    repo_override = _resolve(REGISTRY_REPO_OVERRIDE_RELATIVE_PATH)
    if repo_override.exists():
        data = _load_yaml(repo_override, error=AgentRegistryError)

    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser(), error=AgentRegistryError)
    else:
        env_value = os.environ.get(REGISTRY_ENV_VAR)
        if env_value:
            data = _load_yaml(Path(env_value).expanduser(), error=AgentRegistryError)

    return AgentRegistry.model_validate(data)


def load_model_profiles(override_path: Path | str | None = None) -> dict[str, Any]:
    """Load the Phase 08A model-profiles seed (raw mapping; replacement semantics).

    Authoritative profile *ids* for validation come from
    ``phase_08a_model_profile_contract.json``; this seed carries the operative
    per-profile config (provider/model/temperature/output-mode) and asserts
    ``raw_prompt_persisted``/``raw_response_persisted`` are false.
    """
    seed_path = _resolve(MODEL_PROFILES_SEED_RELATIVE_PATH)
    if not seed_path.exists():
        raise ModelProfilesError(f"Seed model profiles not found at {seed_path}.")

    data: dict[str, Any] = _load_yaml(seed_path, error=ModelProfilesError)

    repo_override = _resolve(MODEL_PROFILES_REPO_OVERRIDE_RELATIVE_PATH)
    if repo_override.exists():
        data = _load_yaml(repo_override, error=ModelProfilesError)

    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser(), error=ModelProfilesError)
    else:
        env_value = os.environ.get(MODEL_PROFILES_ENV_VAR)
        if env_value:
            data = _load_yaml(Path(env_value).expanduser(), error=ModelProfilesError)

    return data
