"""Read-only schema readiness verification (NF-F-001).

The migration-ownership architecture forbids ordinary requests and constructors from migrating or
repairing the managed database. They must instead call this verifier, which performs ONLY read-only
inspection (schema version + optional schedule structural invariants) and raises a typed, actionable
``SchemaReadinessError`` when the database is behind or structurally invalid — never any DDL, repair,
or ``SQLiteMigrator.apply()``.

Guarantees:
- No write transaction, no DDL, no ledger mutation. Reads open the DB immutable/read-only where the
  file exists (works on a read-only snapshot mount); a missing DB / missing ledger reads as version 0.
- Typed failures carry operator guidance directing to the authorized migration/recovery route.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy

from .connection import _ro_connect
from .errors import SchemaStructureInvalid, SchemaVersionBehind
from .migrator import LATEST_SCHEMA_VERSION
from .schedule_schema_verify import (
    verify_v65_schedule_float_schema,
    verify_v80_schedule_package_equivalence_schema,
)

_MIGRATE_GUIDANCE = (
    "run the authorized migration action (admin migrate route or operator-authorized startup "
    "migration with a validated backup receipt); ordinary requests do not migrate the managed DB"
)


def read_schema_version(db_path: Path | None = None, *, conn: sqlite3.Connection | None = None) -> int:
    """Return the highest applied migration version (0 if the DB or ledger is absent). READ-ONLY."""
    if conn is not None:
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    path = Path(db_path) if db_path is not None else PathPolicy().get_db_path()
    if not path.exists():
        return 0
    try:
        with _ro_open(path) as ro:
            row = ro.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def _ro_open(path: Path):
    from contextlib import closing

    return closing(_ro_connect(path))


def schedule_structural_defects(
    db_path: Path | None = None, *, conn: sqlite3.Connection | None = None
) -> list[str]:
    """Return schedule structural invariant violations (empty list = ok). READ-ONLY.

    Reuses the same verifiers ``ensure_schedule_schema`` used, but purely to REPORT — never to repair.
    """
    if conn is not None:
        return list(verify_v65_schedule_float_schema(conn)) + list(
            verify_v80_schedule_package_equivalence_schema(conn)
        )
    path = Path(db_path) if db_path is not None else PathPolicy().get_db_path()
    if not path.exists():
        return ["database_missing"]
    with _ro_open(path) as ro:
        return list(verify_v65_schedule_float_schema(ro)) + list(
            verify_v80_schedule_package_equivalence_schema(ro)
        )


def verify_schema_ready(
    db_path: Path | None = None,
    *,
    require_schedule_schema: bool = False,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Assert the DB is usable for ordinary reads without migration. Returns the schema version.

    Raises ``SchemaVersionBehind`` if below head, or ``SchemaStructureInvalid`` if the requested
    structural invariants are violated. Performs NO mutation.
    """
    version = read_schema_version(db_path, conn=conn)
    if version < LATEST_SCHEMA_VERSION:
        raise SchemaVersionBehind(
            f"managed schema version {version} is behind head {LATEST_SCHEMA_VERSION}",
            guidance=_MIGRATE_GUIDANCE,
        )
    if require_schedule_schema:
        defects = schedule_structural_defects(db_path, conn=conn)
        if defects:
            raise SchemaStructureInvalid(
                f"schedule schema structurally invalid ({len(defects)} invariant(s) violated)",
                guidance=_MIGRATE_GUIDANCE,
            )
    return version


# Storage classes whose migration remains ambient self-heal (RC-1): dev/CLI/test flows that point at
# a non-managed database keep the current "construct = migrate if behind" UX. A managed target
# (production or local), a read-only snapshot, or a blocked/unknown path is NEVER migrated ambiently
# — it must go through an authorized migration route (operator startup / admin migrate, or the
# automatic local app/CLI bootstrap at the entry point).
def self_heal_if_non_managed(db_path: Path | str | None = None) -> int | None:
    """Run ambient self-heal ``SQLiteMigrator.apply()`` ONLY for a non-managed dev / rehearsal /
    workspace target; a no-op (returns ``None``) for managed / snapshot / blocked targets.

    ``apply()`` re-derives the opened-target identity and will still refuse if the file actually
    opened turns out to be managed, so this can never become an ambient managed-migration bypass.
    Returns the resulting schema version when a migration ran, else ``None``.
    """
    from ..config.db_storage_guard import DatabaseStorageClass as SC  # noqa: PLC0415
    from ..config.db_storage_guard import classify_storage_class  # noqa: PLC0415

    path = Path(db_path) if db_path is not None else PathPolicy().get_db_path()
    if classify_storage_class(path) in (
        SC.ISOLATED_WORKSPACE,
        SC.DISPOSABLE_REHEARSAL,
        SC.EXPLICIT_DEVELOPMENT,
    ):
        from .migrator import SQLiteMigrator  # noqa: PLC0415

        return SQLiteMigrator(str(path)).apply()
    return None


def assert_ready_for_use(
    db_path: Path | str | None = None, *, require_schedule_schema: bool = False
) -> int:
    """Constructor/service readiness contract (NF-F-001).

    Non-managed targets self-heal (RC-1, ambient apply preserved). Managed / snapshot targets get a
    READ-ONLY readiness assertion — never migrated here — raising ``SchemaVersionBehind`` /
    ``SchemaStructureInvalid`` with operator guidance when behind or structurally invalid. Returns
    the resulting schema version.
    """
    healed = self_heal_if_non_managed(db_path)
    if healed is not None:
        return healed
    return verify_schema_ready(db_path, require_schedule_schema=require_schedule_schema)


def bootstrap_managed_local_if_behind(db_path: Path | str | None = None) -> int | None:
    """Automatic Mac/CLI-entry self-heal for the canonical MANAGED_LOCAL database ONLY (NF-F-001,
    operator RC-1 decision).

    Resolves and classifies the target; if — and only if — it is exactly the canonical local
    app-support DB and behind head, mints a narrowly-scoped ``LOCAL_APP_BOOTSTRAP`` authorization and
    migrates it to head before any command runs, replacing the removed ambient constructor migration.
    A no-op for a managed-production (NAS), read-only snapshot, workspace, explicit-dev, rehearsal, or
    unknown target. Returns the new version if it migrated, else ``None``.

    Best-effort and hermetic: never raises (invoked at process entry), and is a no-op under pytest so
    it can never touch the real developer database during tests (fixtures self-heal via their own
    ``/tmp`` targets). Returns ``None`` on any error — the command's own readiness gate then reports
    the real problem.
    """
    import os  # noqa: PLC0415

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None

    from ..config.db_storage_guard import DatabaseStorageClass as SC  # noqa: PLC0415
    from ..config.db_storage_guard import classify_storage_class  # noqa: PLC0415

    try:
        path = Path(db_path) if db_path is not None else PathPolicy().get_db_path()
        if classify_storage_class(path) is not SC.MANAGED_LOCAL:
            return None
        current = read_schema_version(path)
        if current >= LATEST_SCHEMA_VERSION:
            return None
        from .migration_authorization import (  # noqa: PLC0415
            acquire_local_bootstrap_capability,
            authorize_migration,
        )
        from .migrator import SQLiteMigrator  # noqa: PLC0415

        authorization = authorize_migration(
            acquire_local_bootstrap_capability(),
            resolved_path=str(path),
            expected_origin_version=current,
            target_version=LATEST_SCHEMA_VERSION,
        )
        return int(SQLiteMigrator(str(path)).apply(authorization=authorization))
    except Exception:  # noqa: BLE001 — best-effort entry hook; readiness gate reports real failures
        return None
