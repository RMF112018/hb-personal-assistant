"""Idempotent writers + DB-backed readers for the v65 decision-support tables.

Writes are UPSERTs keyed on each table's deterministic PRIMARY KEY (no new schema);
``created_utc`` and the conflict-key columns are never overwritten, so re-running an apply
is idempotent. Readers return the projected ``raw_json`` (``json.loads``) for parity-style
checks, plus a few typed column readers used by tests/assertions.

Populated this phase: maturity snapshot, data-availability profiles, confidence scorecards
+ factors. The remaining v65 tables (method eligibility, model-selection, operator/required
assumptions) ship empty until a follow-on slice.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

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


def upsert_maturity_snapshot(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_project_maturity_snapshots", row, ("snapshot_id",))


def upsert_availability_profile(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_data_availability_profiles", row, ("id",))


def upsert_confidence_scorecard(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_confidence_scorecards", row, ("scorecard_id",))


def upsert_confidence_factor(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_confidence_factors", row, ("id",))


# Maps the engine's planned-table keys to their per-row upsert helper.
_WRITERS = {
    "maturity": upsert_maturity_snapshot,
    "availability": upsert_availability_profile,
    "scorecards": upsert_confidence_scorecard,
    "factors": upsert_confidence_factor,
}


def apply_plan(
    conn: sqlite3.Connection, planned: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    """Upsert every planned row into the populated v65 tables. Returns per-key written counts."""
    for key, writer in _WRITERS.items():
        for row in planned.get(key, []):
            writer(conn, row)
    return {key: len(planned.get(key, [])) for key in _WRITERS}


def _read_raw(
    conn: sqlite3.Connection, table: str, where_col: str, where_val: str, order_by: str
) -> list[dict[str, Any]]:
    sql = f"SELECT raw_json FROM {table} WHERE {where_col} = ? ORDER BY {order_by}"
    return [json.loads(r[0]) for r in conn.execute(sql, (where_val,))]


def read_maturity_from_db(conn: sqlite3.Connection, *, run_id: str) -> list[dict[str, Any]]:
    return _read_raw(
        conn, "forecast_project_maturity_snapshots", "run_id", run_id, "snapshot_id"
    )


def read_availability_from_db(conn: sqlite3.Connection, *, run_id: str) -> list[dict[str, Any]]:
    return _read_raw(conn, "forecast_data_availability_profiles", "run_id", run_id, "domain")


def read_scorecards_from_db(conn: sqlite3.Connection, *, run_id: str) -> list[dict[str, Any]]:
    return _read_raw(
        conn, "forecast_confidence_scorecards", "run_id", run_id, "scope, scope_key"
    )


def read_factors_for_scorecard(
    conn: sqlite3.Connection, *, scorecard_id: str
) -> list[dict[str, Any]]:
    return _read_raw(
        conn, "forecast_confidence_factors", "scorecard_id", scorecard_id, "factor_key"
    )


def maturity_tier(conn: sqlite3.Connection, *, run_id: str) -> str | None:
    """The maturity_tier column for a run's snapshot (typed read for assertions)."""
    row = conn.execute(
        "SELECT maturity_tier FROM forecast_project_maturity_snapshots WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    return row[0] if row else None
