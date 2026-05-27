"""Construction source-registry loader.

Loads the seeded YAML inventory of SharePoint/OneDrive sources and validates it
against the Pydantic models in :mod:`hb_assistant.construction.config.models`.

Search order (later wins; replacement semantics, matching ``config/loader.py``):

1. Built-in seed at ``resources/config/sharepoint_onedrive_sources.seed.yaml``
   (resolved relative to repo root via :meth:`PathPolicy.resolve_repo_root`).
2. Optional repo override at ``config/construction_sources.yml``.
3. Explicit ``override_path`` argument.
4. Environment variable ``HB_CONSTRUCTION_SOURCES``.

The seed file ships with ``resolution_status: pending`` on every source by
design — real ``site_id`` / ``drive_id`` values land via subsequent prompts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from .models import SourceRegistry

SEED_RELATIVE_PATH = Path("resources") / "config" / "sharepoint_onedrive_sources.seed.yaml"
REPO_OVERRIDE_RELATIVE_PATH = Path("config") / "construction_sources.yml"
ENV_VAR = "HB_CONSTRUCTION_SOURCES"


class SourceRegistryError(RuntimeError):
    """Raised when the source registry cannot be loaded or validated."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SourceRegistryError(
            f"Source registry file {path} must contain a mapping at top level"
        )
    return data


def _resolve_seed_path() -> Path:
    repo_root = PathPolicy().resolve_repo_root()
    return repo_root / SEED_RELATIVE_PATH


def _resolve_repo_override_path() -> Path:
    repo_root = PathPolicy().resolve_repo_root()
    return repo_root / REPO_OVERRIDE_RELATIVE_PATH


def load_source_registry(override_path: Path | str | None = None) -> SourceRegistry:
    """Load and validate the construction-agent source registry.

    Raises :class:`SourceRegistryError` if the seed is missing or any input
    file is malformed; raises :class:`pydantic.ValidationError` if the merged
    data fails schema validation.
    """

    seed_path = _resolve_seed_path()
    if not seed_path.exists():
        raise SourceRegistryError(
            f"Seed source registry not found at {seed_path}. "
            "Construction-agent cannot start without the seeded inventory."
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

    return SourceRegistry.model_validate(data)
