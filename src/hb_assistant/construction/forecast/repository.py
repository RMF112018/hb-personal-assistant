"""Idempotent writers for the five v58 forecast foundation tables.

All writes are UPSERTs keyed on the tables' existing PRIMARY KEY / UNIQUE
constraints (no new schema). ``created_utc`` and the conflict-key columns are never
overwritten on re-projection, so re-running ``apply`` is idempotent.
"""

from __future__ import annotations

import sqlite3
from typing import Any

# Columns of each v58 table, in insert order (must match migrator.py V58_STATEMENTS).
FORECAST_PROJECTS_COLS = (
    "project_key",
    "project_name",
    "job_number",
    "enabled",
    "created_utc",
    "updated_utc",
)
FORECAST_RUNS_COLS = ("run_id", "project_key", "context_package", "status", "notes", "created_utc")
FORECAST_SOURCE_INGESTIONS_COLS = (
    "ingestion_id",
    "project_key",
    "run_id",
    "source_kind",
    "source_package",
    "source_path",
    "source_sha256",
    "row_count",
    "created_utc",
)
FORECAST_PACKAGE_MANIFESTS_COLS = (
    "package_id",
    "project_key",
    "run_id",
    "package_type",
    "package_name",
    "package_stamp",
    "upstream_packages",
    "source_data_hashes",
    "row_counts",
    "validation_passed",
    "validation_conclusion",
    "file_path",
    "created_utc",
)
FORECAST_VALIDATION_EVENTS_COLS = (
    "run_id",
    "event_seq",
    "project_key",
    "gate_name",
    "status",
    "detail",
    "created_utc",
)

# Columns never overwritten on conflict, beyond the conflict-key columns themselves.
_IMMUTABLE = {"created_utc"}


def _upsert(
    conn: sqlite3.Connection,
    table: str,
    values: dict[str, Any],
    conflict_cols: tuple[str, ...],
) -> None:
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


def upsert_project(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_projects", row, ("project_key",))


def upsert_run(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_runs", row, ("run_id",))


def upsert_source_ingestion(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    # ingestion_id is derived deterministically from (project_key|source_package|source_sha256),
    # so the PK conflict target is consistent with the UNIQUE(project_key, source_package, source_sha256).
    _upsert(conn, "forecast_source_ingestions", row, ("ingestion_id",))


def upsert_package_manifest(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_package_manifests", row, ("package_id",))


def upsert_validation_event(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_validation_events", row, ("run_id", "event_seq"))


def apply_plan(
    conn: sqlite3.Connection, planned: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    """Upsert every planned row into the five v58 tables. Returns per-table written counts."""
    for row in planned["projects"]:
        upsert_project(conn, row)
    for row in planned["runs"]:
        upsert_run(conn, row)
    for row in planned["package_manifests"]:
        upsert_package_manifest(conn, row)
    for row in planned["source_ingestions"]:
        upsert_source_ingestion(conn, row)
    for row in planned["validation_events"]:
        upsert_validation_event(conn, row)
    return {key: len(rows) for key, rows in planned.items()}
