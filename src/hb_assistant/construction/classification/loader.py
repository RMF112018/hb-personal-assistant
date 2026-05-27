"""Construction Ollama model-routing loader.

Loads the seeded YAML configuration and validates against
:mod:`hb_assistant.construction.classification.models`.

Search order (later wins; replacement semantics, matching
``construction/config/loader.py`` and ``construction/policy/loader.py``):

1. Built-in seed at ``resources/config/ollama_model_routing.seed.yaml``.
2. Optional repo override at ``config/ollama_model_routing.yml``.
3. Explicit ``override_path`` argument.
4. Environment variable ``HB_CONSTRUCTION_MODEL_ROUTING``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from .models import ModelRoutingConfig

SEED_RELATIVE_PATH = Path("resources") / "config" / "ollama_model_routing.seed.yaml"
REPO_OVERRIDE_RELATIVE_PATH = Path("config") / "ollama_model_routing.yml"
ENV_VAR = "HB_CONSTRUCTION_MODEL_ROUTING"


class ModelRoutingError(RuntimeError):
    """Raised when the Ollama routing config cannot be loaded."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ModelRoutingError(
            f"Ollama routing config {path} must contain a mapping at top level"
        )
    return data


def _resolve_seed_path() -> Path:
    return PathPolicy().resolve_repo_root() / SEED_RELATIVE_PATH


def _resolve_repo_override_path() -> Path:
    return PathPolicy().resolve_repo_root() / REPO_OVERRIDE_RELATIVE_PATH


def load_model_routing_config(
    override_path: Path | str | None = None,
) -> ModelRoutingConfig:
    """Load and validate the construction-agent Ollama routing config.

    Raises :class:`ModelRoutingError` if the seed is missing or any file is
    malformed; raises :class:`pydantic.ValidationError` if the merged data
    fails schema validation.
    """

    seed_path = _resolve_seed_path()
    if not seed_path.exists():
        raise ModelRoutingError(
            f"Seed Ollama routing config not found at {seed_path}. "
            "Construction-agent classifier cannot start without a routing config."
        )

    data: dict[str, Any] = _load_yaml(seed_path)

    repo_override = _resolve_repo_override_path()
    if repo_override.exists():
        data = _load_yaml(repo_override)

    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser())
    else:
        env_value = os.environ.get(ENV_VAR)
        if env_value:
            data = _load_yaml(Path(env_value).expanduser())

    return ModelRoutingConfig.model_validate(data)
