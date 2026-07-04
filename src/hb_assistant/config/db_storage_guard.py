"""Fail-closed guard for SQLite DB storage locality (NAS-local vs network mounts).

Universal deny: ``/Volumes/*``, ``smb://``, ``nfs://``, UNC-like paths, relative paths.
When ``HB_NAS_RUNTIME=1``, only NAS-local managed DB paths under ``/volume2/personal-assistant/``
are permitted. ``HB_DB_STORAGE_GUARD=permissive`` is ignored when ``HB_NAS_RUNTIME=1``.
"""

from __future__ import annotations

import os
from pathlib import Path

from hb_assistant.config.db_path_guard import is_under_clean_db_copy

NAS_VOLUME_PREFIX = "/volume2/personal-assistant/"
NAS_DEFAULT_DB_PATH = (
    "/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite"
)
MANAGED_DB_FILENAME = "hb-personal-assistant.sqlite"
MAC_APP_SUPPORT_NAME = "HB Personal Assistant"


class DbStorageGuardError(Exception):
    """Raised when a DB path resolves to disallowed storage."""

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        path: str,
        storage_class: str = "blocked",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path
        self.storage_class = storage_class


def is_nas_runtime() -> bool:
    return os.environ.get("HB_NAS_RUNTIME", "").strip() == "1"


def nas_on_demand_watch_allowed() -> bool:
    """Whether on-demand watcher START/RESTART is permitted.

    Outside NAS runtime: always allowed (dev/Mac operator control). Under ``HB_NAS_RUNTIME=1`` the
    watcher is default-off and on-demand starts are refused unless the operator opts in
    deliberately with ``HB_NAS_ALLOW_WATCH=1`` (single-writer ownership then rests on the lease).
    """
    if not is_nas_runtime():
        return True
    return os.environ.get("HB_NAS_ALLOW_WATCH", "").strip() == "1"


def is_permissive_guard() -> bool:
    if is_nas_runtime():
        return False
    return os.environ.get("HB_DB_STORAGE_GUARD", "").strip().lower() == "permissive"


def _is_unc_like(raw: str) -> bool:
    if raw.startswith("\\\\"):
        return True
    if raw.startswith("//") and not raw.startswith("///"):
        return True
    return False


def _resolve_path(db_path: str | Path) -> Path | None:
    try:
        expanded = Path(db_path).expanduser()
        if not expanded.is_absolute():
            return None
        return expanded.resolve()
    except Exception:
        return None


def _universal_deny_reason(raw: str, resolved: Path | None) -> str | None:
    expanded = str(Path(raw).expanduser())
    low = expanded.lower()
    if low.startswith("smb:") or low.startswith("nfs:"):
        return "network_scheme"
    if expanded.startswith("/Volumes/"):
        return "mac_smb_mount"
    if _is_unc_like(expanded):
        return "unc_path"
    if not Path(raw).expanduser().is_absolute():
        return "relative_path"
    if resolved is None:
        return "unresolvable_path"
    return None


def _mac_managed_db_path() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / MAC_APP_SUPPORT_NAME
        / "db"
        / MANAGED_DB_FILENAME
    ).resolve()


def _is_nas_managed_db(resolved: Path) -> bool:
    resolved_str = str(resolved)
    if not resolved_str.startswith(NAS_VOLUME_PREFIX):
        return False
    if resolved.name != MANAGED_DB_FILENAME:
        return False
    if resolved.parent.name != "db":
        return False
    return True


def classify_db_storage(db_path: str | Path) -> str:
    """Return a storage class label for ``db_path``."""
    raw = str(db_path)
    resolved = _resolve_path(db_path)
    if _universal_deny_reason(raw, resolved) is not None:
        return "blocked"

    assert resolved is not None

    if is_nas_runtime():
        return "nas_local" if _is_nas_managed_db(resolved) else "blocked"

    if is_permissive_guard():
        return "dev_permissive"

    try:
        if resolved == _mac_managed_db_path():
            return "mac_local"
    except Exception:
        pass

    if is_under_clean_db_copy(resolved):
        return "clean_db_copy"

    return "dev_permissive"


def assert_db_storage_allowed(db_path: str | Path, *, context: str = "db_open") -> str:
    """Validate ``db_path``; return storage class or raise ``DbStorageGuardError``."""
    raw = str(db_path)
    resolved = _resolve_path(db_path)
    deny = _universal_deny_reason(raw, resolved)
    if deny is not None:
        raise DbStorageGuardError(
            f"refusing {context}: disallowed DB storage ({deny})",
            reason=deny,
            path=raw,
            storage_class="blocked",
        )

    storage_class = classify_db_storage(db_path)
    if storage_class == "blocked":
        reason = "nas_local_path_required" if is_nas_runtime() else "unapproved_local_path"
        raise DbStorageGuardError(
            f"refusing {context}: DB path is not an approved storage location",
            reason=reason,
            path=raw,
            storage_class=storage_class,
        )
    return storage_class


def nas_default_db_path() -> Path:
    return Path(NAS_DEFAULT_DB_PATH)
