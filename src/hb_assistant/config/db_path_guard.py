"""Neutral live-DB path guard for schedule, forecast, and operator tooling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

CLEAN_DB_SUBDIR = "local-sensitive/clean-db"


def get_live_db_path() -> Path:
    return PathPolicy().get_db_path().resolve()


def is_live_db_path(db_path: str | Path) -> bool:
    """True when ``db_path`` resolves to the live/default DB, or resolution fails (fail-closed)."""
    try:
        return Path(db_path).resolve() == get_live_db_path()
    except Exception:
        return True


def is_under_clean_db_copy(db_path: str | Path, *, repo_root: Path | None = None) -> bool:
    root = (repo_root or PathPolicy().resolve_repo_root()).resolve()
    try:
        resolved = Path(db_path).resolve()
        clean_root = (root / CLEAN_DB_SUBDIR).resolve()
        return resolved == clean_root or clean_root in resolved.parents
    except Exception:
        return False


def resolve_clean_copy_guard(
    db_path: str | Path,
    *,
    allow_custom_copy_path: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    resolved = str(Path(db_path).expanduser())
    live = is_live_db_path(resolved)
    under_clean = is_under_clean_db_copy(resolved, repo_root=repo_root)
    allowed = (not live) and (under_clean or allow_custom_copy_path)
    return {
        "db_path": resolved,
        "db_path_is_live_db": live,
        "clean_copy_guard_passed": allowed,
        "under_clean_db_copy": under_clean,
        "allow_custom_copy_path": allow_custom_copy_path,
        "live_db_protection": live is False,
    }


def assert_not_live_db(db_path: str | Path, *, context: str = "mutation") -> None:
    if is_live_db_path(db_path):
        raise ValueError(f"refusing {context} against live database path")


def assert_clean_copy_path(
    db_path: str | Path,
    *,
    allow_custom_copy_path: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    guard = resolve_clean_copy_guard(
        db_path,
        allow_custom_copy_path=allow_custom_copy_path,
        repo_root=repo_root,
    )
    if guard["db_path_is_live_db"]:
        raise ValueError("refusing operation against live database path")
    if not guard["clean_copy_guard_passed"]:
        raise ValueError(
            f"db_path must be under {CLEAN_DB_SUBDIR}/ unless --allow-custom-copy-path is set"
        )
    return guard
