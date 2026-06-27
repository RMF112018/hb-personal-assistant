"""Shared helpers for the Project Staffing repositories (Phase 2a).

Mirrors the conventions in ``store/forecast_generation_request_repository.py`` and
``construction/forecast/source_domain_repository.py``: seconds-precision UTC stamps, uuid12 ids,
a generic idempotent upsert that never overwrites ``created_utc``, and a lightweight schema-version
gate so callers fail clearly when run against a pre-V76 database.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

REQUIRED_SCHEMA_VERSION = 76

# Columns an upsert must never overwrite on conflict.
_IMMUTABLE = frozenset({"created_utc"})


class StaffingStoreError(RuntimeError):
    """Raised when the staffing store is not ready (e.g. schema below V76)."""


def utc_now() -> str:
    """Seconds-precision ISO-8601 UTC (matches the forecast repositories)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def assert_schema(conn: sqlite3.Connection, *, minimum: int = REQUIRED_SCHEMA_VERSION) -> None:
    """Fail closed when the DB schema is older than the staffing tables require."""
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    except sqlite3.OperationalError as exc:  # pragma: no cover - unmigrated DB
        raise StaffingStoreError("schema_migrations table missing") from exc
    version = int(row[0]) if row and row[0] is not None else 0
    if version < minimum:
        raise StaffingStoreError(f"staffing schema v{minimum} required, found v{version}")


def upsert(
    conn: sqlite3.Connection,
    table: str,
    values: dict[str, Any],
    conflict_cols: tuple[str, ...],
) -> None:
    """Idempotent INSERT ... ON CONFLICT upsert. ``created_utc`` is never overwritten."""
    cols = list(values)
    placeholders = ", ".join("?" for _ in cols)
    frozen = set(conflict_cols) | _IMMUTABLE
    assignments = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in frozen)
    conflict = ", ".join(conflict_cols)
    if assignments:
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict}) DO UPDATE SET {assignments}"
        )
    else:
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict}) DO NOTHING"
        )
    conn.execute(sql, tuple(values[c] for c in cols))
