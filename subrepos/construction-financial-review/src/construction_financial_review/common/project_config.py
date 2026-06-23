"""CFR-local project-config loader (P4b).

Resolves which project a generator runs for, and loads its `config/projects/<key>.json`.
Generators run as subprocesses (the CLI shells out via `sys.executable`), so the project is
selected by the ``CFR_PROJECT_KEY`` environment variable (default ``tropical`` — byte-identical
to the historical hardcoded behavior). The loaded config is the single source of every
project-specific value the generators previously hardcoded.

Stdlib + CFR-internal only (no ``hb_assistant`` import): reuses ``common/io.read_json`` and the
``common/config_root`` base resolver, and fail-closes ineligible projects via
``common/project_eligibility`` so a generator can never run for an unapproved project.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config_root import resolve_config_base
from .io import read_json
from .project_eligibility import is_project_eligible

# subrepo root: <root>/src/construction_financial_review/common/project_config.py -> parents[3]
SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_PROJECT_KEY = "CFR_PROJECT_KEY"
DEFAULT_PROJECT_KEY = "tropical"


class ProjectConfigError(RuntimeError):
    """Raised when a project config is missing, ineligible, or unreadable (fail closed)."""


def resolve_project_key() -> str:
    """The project key a generator should run for: ``CFR_PROJECT_KEY`` env, else ``tropical``."""
    raw = os.environ.get(ENV_PROJECT_KEY, "").strip()
    return raw or DEFAULT_PROJECT_KEY


def project_config_path(project_key: str) -> Path:
    """Path to ``config/projects/<project_key>.json`` (honors the CFR_CONFIG_ROOT bridge)."""
    base = resolve_config_base(SUBPROJECT_ROOT)
    return Path(base) / "config" / "projects" / f"{project_key}.json"


def load_project_config(project_key: str | None = None) -> dict[str, Any]:
    """Load the project config dict (fail closed).

    Resolves ``project_key`` from the env when omitted. Refuses an ineligible project before any
    file access, and raises ``ProjectConfigError`` when the config file is absent or unreadable.
    """
    key = project_key if project_key is not None else resolve_project_key()
    if not is_project_eligible(key):
        raise ProjectConfigError(f"project_key {key!r} is not eligible; refusing to load its config")
    path = project_config_path(key)
    if not path.is_file():
        raise ProjectConfigError(f"project config not found for {key!r}: {path}")
    try:
        cfg = read_json(path)
    except (OSError, ValueError) as exc:
        raise ProjectConfigError(f"project config for {key!r} is unreadable: {path} ({exc})") from exc
    if not isinstance(cfg, dict):
        raise ProjectConfigError(f"project config for {key!r} is not a JSON object: {path}")
    if cfg.get("project_key") != key:
        raise ProjectConfigError(
            f"project config project_key {cfg.get('project_key')!r} != requested {key!r}: {path}"
        )
    return cfg
