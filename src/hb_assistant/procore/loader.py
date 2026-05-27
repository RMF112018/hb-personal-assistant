"""Loaders for the Procore endpoint contract and projects registry.

Two independent files, each with the same precedence pattern used by every
other construction-agent loader:

1. Built-in seed under ``resources/config/`` (resolved via PathPolicy).
2. Optional repo override at ``config/<basename>.yml``.
3. Explicit ``override_path`` argument.
4. Environment variable (``HB_PROCORE_ENDPOINT_CONTRACT`` /
   ``HB_PROCORE_PROJECTS``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from .models import ProcoreEndpointContract, ProcoreProjectsRegistry

# Endpoint contract
CONTRACT_SEED_RELATIVE = Path("resources") / "config" / "procore_endpoint_contract.seed.yaml"
CONTRACT_REPO_OVERRIDE_RELATIVE = Path("config") / "procore_endpoint_contract.yml"
CONTRACT_ENV_VAR = "HB_PROCORE_ENDPOINT_CONTRACT"

# Projects registry
PROJECTS_SEED_RELATIVE = Path("resources") / "config" / "procore_projects.seed.yaml"
PROJECTS_REPO_OVERRIDE_RELATIVE = Path("config") / "procore_projects.yml"
PROJECTS_ENV_VAR = "HB_PROCORE_PROJECTS"


class EndpointContractError(RuntimeError):
    """Raised when the Procore endpoint contract cannot be loaded."""


class ProcoreProjectsError(RuntimeError):
    """Raised when the Procore projects registry cannot be loaded."""


def _load_yaml(path: Path, error_cls: type[RuntimeError]) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise error_cls(f"{path} must contain a mapping at top level")
    return data


def _resolve(relative: Path) -> Path:
    return PathPolicy().resolve_repo_root() / relative


def load_endpoint_contract(
    override_path: Path | str | None = None,
) -> ProcoreEndpointContract:
    seed = _resolve(CONTRACT_SEED_RELATIVE)
    if not seed.exists():
        raise EndpointContractError(
            f"Seed Procore endpoint contract not found at {seed}. "
            "Procore audit cannot start without the seeded contract."
        )
    data = _load_yaml(seed, EndpointContractError)
    repo_override = _resolve(CONTRACT_REPO_OVERRIDE_RELATIVE)
    if repo_override.exists():
        data = _load_yaml(repo_override, EndpointContractError)
    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser(), EndpointContractError)
    else:
        env_value = os.environ.get(CONTRACT_ENV_VAR)
        if env_value:
            data = _load_yaml(Path(env_value).expanduser(), EndpointContractError)
    return ProcoreEndpointContract.model_validate(data)


def load_procore_projects(
    override_path: Path | str | None = None,
) -> ProcoreProjectsRegistry:
    seed = _resolve(PROJECTS_SEED_RELATIVE)
    if not seed.exists():
        raise ProcoreProjectsError(
            f"Seed Procore projects registry not found at {seed}. "
            "Procore audit cannot start without the seeded projects mapping."
        )
    data = _load_yaml(seed, ProcoreProjectsError)
    repo_override = _resolve(PROJECTS_REPO_OVERRIDE_RELATIVE)
    if repo_override.exists():
        data = _load_yaml(repo_override, ProcoreProjectsError)
    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser(), ProcoreProjectsError)
    else:
        env_value = os.environ.get(PROJECTS_ENV_VAR)
        if env_value:
            data = _load_yaml(Path(env_value).expanduser(), ProcoreProjectsError)
    return ProcoreProjectsRegistry.model_validate(data)
