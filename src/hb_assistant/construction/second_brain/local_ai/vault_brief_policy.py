"""Phase 10 correction — governed daily-brief vault folder resolution (config-backed + guarded).

The scheduled daily brief must land in the operator's governed brief folder
(``<vault>/Work/Daily Brief``), declared by the ``phase_10_obsidian_vault_policy`` seed
(``target_daily_brief_folder`` + ``allowlisted_folders``). The earlier failure wrote into the
legacy ``Construction Intelligence/Phase 08A Daily Briefs`` folder because the writer hardcoded that
subdir and ignored the policy.

This module is the single source of truth for the governed folder:

- it loads + validates the vault policy (fail-closed via :func:`load_obsidian_vault_policy`),
- it refuses to resolve the legacy Phase 08A folder unless an explicit override env var is set, and
- it exposes a redacted (relative-to-home) string form for status surfaces.

Read-only: no DB, no writeback, no network.
"""

from __future__ import annotations

import os
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy

from .contracts import Phase10ContractError, load_obsidian_vault_policy

#: The legacy folder that the first scheduled run wrote to by mistake — guarded against.
LEGACY_BRIEF_SUBDIR = Path("Construction Intelligence") / "Phase 08A Daily Briefs"

#: Escape hatch: only an explicit operator override may re-enable the legacy folder.
LEGACY_OVERRIDE_ENV = "HB_ALLOW_LEGACY_BRIEF_DIR"


class VaultBriefPolicyError(RuntimeError):
    """Raised when the governed brief folder cannot be resolved safely (fail-closed)."""


def _legacy_override_enabled() -> bool:
    return os.environ.get(LEGACY_OVERRIDE_ENV, "").strip() in {"1", "true", "True", "yes"}


def governed_brief_subdir() -> Path:
    """The policy-declared brief subdir (relative to the vault root), validated + guarded."""
    try:
        policy = load_obsidian_vault_policy()
    except (
        Phase10ContractError
    ) as exc:  # fail-closed: never silently fall back to the legacy folder
        raise VaultBriefPolicyError(f"obsidian vault policy unavailable: {exc}") from exc
    folder = policy.target_daily_brief_folder
    subdir = Path(folder)
    # The policy model already asserts the target is allowlisted; double-guard the legacy folder here.
    if subdir == LEGACY_BRIEF_SUBDIR and not _legacy_override_enabled():
        raise VaultBriefPolicyError(
            "refusing legacy Phase 08A brief folder; set "
            f"{LEGACY_OVERRIDE_ENV}=1 only to intentionally override"
        )
    return subdir


def governed_brief_dir(*, path_policy: PathPolicy | None = None) -> Path:
    """Absolute governed brief directory: ``<vault_root>/<target_daily_brief_folder>``."""
    pp = path_policy or PathPolicy()
    return pp.get_vault_root() / governed_brief_subdir()


def is_legacy_brief_dir(target: str | Path) -> bool:
    """True when ``target`` resolves under the guarded legacy Phase 08A folder."""
    t = Path(target)
    return LEGACY_BRIEF_SUBDIR.as_posix() in t.as_posix()


def assert_not_legacy(target: str | Path) -> None:
    """Fail-closed guard: refuse a resolved brief path inside the legacy folder (unless overridden)."""
    if is_legacy_brief_dir(target) and not _legacy_override_enabled():
        raise VaultBriefPolicyError(
            f"refusing to write the daily brief into the legacy Phase 08A folder: {target!s}; "
            f"set {LEGACY_OVERRIDE_ENV}=1 only to intentionally override"
        )


def redacted_brief_dir(*, path_policy: PathPolicy | None = None) -> str:
    """Redacted (``~/…``) governed brief directory for status surfaces; never an absolute op path."""
    target = governed_brief_dir(path_policy=path_policy)
    try:
        return "~/" + str(target.resolve().relative_to(Path.home()))
    except ValueError:
        return f"{target.parent.name}/{target.name}"
