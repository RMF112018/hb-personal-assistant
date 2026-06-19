"""Opt-in config-root bridge (Phase 16).

Forecast config is normally resolved relative to a fixed ``SUBPROJECT_ROOT`` (the construction-financial-
review checkout). Phase 16 adds a single, explicit, opt-in override so a materialized DB config snapshot
can be fed to the EXISTING file-backed readers without rewriting them:

    CFR_CONFIG_ROOT=<absolute dir containing a config/ subtree>

Contract (fail closed):
  - unset            -> returns the caller's hardcoded ``subproject_root`` (byte-identical behavior).
  - set + valid      -> returns that directory (used as the base the ``config/...`` relative paths join to).
  - set + invalid    -> raises ``ConfigRootError`` (must be an existing absolute directory).

This is a narrow compatibility bridge, NOT a production default: only Phase 16 materialization and the
``validate-crosswalk`` DB-snapshot path set it (scoped, try/finally restored). It is never set globally.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_CONFIG_ROOT = "CFR_CONFIG_ROOT"


class ConfigRootError(RuntimeError):
    """Raised when CFR_CONFIG_ROOT is set but is not an existing absolute directory (fail closed)."""


def config_root_override() -> Path | None:
    """Return the validated CFR_CONFIG_ROOT override, or None when unset. Fail closed if set-but-invalid."""
    raw = os.environ.get(ENV_CONFIG_ROOT)
    if raw is None or raw == "":
        return None
    p = Path(raw)
    if not p.is_absolute():
        raise ConfigRootError(f"{ENV_CONFIG_ROOT} must be an absolute path: {raw!r}")
    if not p.exists():
        raise ConfigRootError(f"{ENV_CONFIG_ROOT} does not exist: {p}")
    if not p.is_dir():
        raise ConfigRootError(f"{ENV_CONFIG_ROOT} is not a directory: {p}")
    return p


def resolve_config_base(subproject_root: Path) -> Path:
    """Base directory the ``config/...`` relative paths join to: the override if set, else subproject_root."""
    override = config_root_override()
    return override if override is not None else Path(subproject_root)
