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
