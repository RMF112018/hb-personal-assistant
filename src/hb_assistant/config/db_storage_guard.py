"""Fail-closed guard for SQLite DB storage locality (NAS-local vs network mounts).

Universal deny: ``/Volumes/*``, ``smb://``, ``nfs://``, UNC-like paths, relative paths.
When ``HB_NAS_RUNTIME=1``, only NAS-local managed DB paths under ``/volume2/personal-assistant/``
are permitted. ``HB_DB_STORAGE_GUARD=permissive`` is ignored when ``HB_NAS_RUNTIME=1``.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from hb_assistant.config.db_path_guard import is_under_clean_db_copy

NAS_VOLUME_PREFIX = "/volume2/personal-assistant/"
NAS_DEFAULT_DB_PATH = (
    "/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite"
)
# The internet-facing NAS MCP reads a bind-mounted read-only snapshot of the managed DB at this
# path (mcp-snapshot), and routes connected-client staging writes to a separate writable workspace
# DB (mcp-workspace). These share the NAS prefix + ``db`` parent + managed filename with the managed
# production DB, so filename/parent pattern-matching cannot tell them apart (NF-F-001 RC-2) — the
# authorization storage-class classifier below uses EXACT-PATH equality against the configured roots.
NAS_SNAPSHOT_DB_PATH = (
    "/volume2/personal-assistant/app-support/mcp-snapshot/db/hb-personal-assistant.sqlite"
)
MANAGED_DB_FILENAME = "hb-personal-assistant.sqlite"
MAC_APP_SUPPORT_NAME = "HB Personal Assistant"


class DatabaseStorageClass(str, Enum):
    """Non-interchangeable storage classes for the migration-ownership boundary (NF-F-001).

    Distinct from the legacy locality labels returned by ``classify_db_storage`` (which answer
    "is this an allowed place to open a DB?"). These answer "what *kind* of managed target is this,
    for authorization?" and are bound into ``MigrationAuthorization``. Classification is by
    EXACT-PATH equality against the configured managed/workspace/snapshot roots (RC-2) so a
    workspace- or snapshot-shaped path can never be authorized as managed production.
    """

    MANAGED_PRODUCTION = "managed_production"  # NAS canonical DB — strict operator authorization
    MANAGED_LOCAL = "managed_local"  # Mac app-support canonical DB — auto local-bootstrap at entry
    ISOLATED_WORKSPACE = "isolated_workspace"
    READ_ONLY_SNAPSHOT = "read_only_snapshot"
    DISPOSABLE_REHEARSAL = "disposable_rehearsal"
    EXPLICIT_DEVELOPMENT = "explicit_development"  # ONLY an explicitly-selected dev DB — never inferred
    BLOCKED = "blocked"


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


def snapshot_db_path() -> Path:
    """Resolve the read-only snapshot DB path (``HB_ASSISTANT_SNAPSHOT_DB`` or the NAS default).

    RC-2: an explicit accessor for the read-only snapshot root so the storage-class classifier can
    distinguish it from the managed production DB by exact path rather than by shared filename/parent.
    Optional env override (unset on dev hosts; the NAS compose pins the mount path via mcp config).
    """
    raw = os.environ.get("HB_ASSISTANT_SNAPSHOT_DB", "").strip()
    return Path(raw) if raw else Path(NAS_SNAPSHOT_DB_PATH)


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return False


def classify_storage_class(db_path: str | Path) -> DatabaseStorageClass:
    """Classify ``db_path`` into a ``DatabaseStorageClass`` for the migration-ownership boundary.

    EXACT-PATH equality against the configured managed / workspace / snapshot roots (RC-2) — a
    workspace- or snapshot-shaped path is NEVER classified as managed production. Fails closed:
    universally-denied paths → ``BLOCKED``; unknown NAS-runtime paths → ``BLOCKED``. Managed is
    matched first, so a development/rehearsal path can never shadow the managed target.
    """
    raw = str(db_path)
    resolved = _resolve_path(db_path)
    if _universal_deny_reason(raw, resolved) is not None:
        return DatabaseStorageClass.BLOCKED
    assert resolved is not None

    # Exact-path equality against the configured roots (import workspace lazily to avoid the
    # store.workspace -> migrator -> connection -> db_storage_guard import cycle). Managed classes
    # are matched FIRST so a dev/rehearsal path can never shadow a managed target.
    from hb_assistant.store.workspace import workspace_db_path  # noqa: PLC0415

    if _same_path(resolved, nas_default_db_path()):
        return DatabaseStorageClass.MANAGED_PRODUCTION
    if _same_path(resolved, _mac_managed_db_path()):
        return DatabaseStorageClass.MANAGED_LOCAL
    if _same_path(resolved, workspace_db_path()):
        return DatabaseStorageClass.ISOLATED_WORKSPACE
    if _same_path(resolved, snapshot_db_path()):
        return DatabaseStorageClass.READ_ONLY_SNAPSHOT
    if is_under_clean_db_copy(resolved) or _is_temp_fixture(resolved):
        return DatabaseStorageClass.DISPOSABLE_REHEARSAL

    # EXPLICIT_DEVELOPMENT is NEVER inferred merely because a path is local — it must be the DB the
    # operator explicitly selected via HB_ASSISTANT_DEV_DB (exact match).
    dev = os.environ.get("HB_ASSISTANT_DEV_DB", "").strip()
    if dev and _same_path(resolved, Path(dev)):
        return DatabaseStorageClass.EXPLICIT_DEVELOPMENT

    # Anything else fails closed — no broad local exception that could become an authorization bypass.
    return DatabaseStorageClass.BLOCKED


def _is_temp_fixture(resolved: Path) -> bool:
    """True when ``resolved`` lives under a system temp root (test/rehearsal fixtures). Bounded — not
    a general 'any local path' rule."""
    import contextlib  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    roots = {"/tmp", "/private/tmp", "/private/var/folders", "/var/folders"}
    with contextlib.suppress(Exception):
        roots.add(str(Path(tempfile.gettempdir()).resolve()))
    rs = str(resolved)
    return any(rs == r or rs.startswith(r + "/") for r in roots)
