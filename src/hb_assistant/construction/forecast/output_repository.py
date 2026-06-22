"""Idempotent writers + DB-backed read repositories for the v63 run-output tables.

Writes are UPSERTs keyed on each table's UNIQUE/PRIMARY constraint (no new schema);
``created_utc`` and the conflict-key columns are never overwritten, so re-running an
apply is idempotent. Read repositories return the projected row's ``raw_json``
(``json.loads``) and nothing else, so a parity test can compare DB output against the
source package rows (canonical row-equivalence).

Scope this phase: the header (``forecast_outputs``), per-code recommendations
(``forecast_output_budget_codes``), and the risk register (``forecast_output_risks``).
The remaining v63 tables ship empty until a follow-on projection slice.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

FORECAST_OUTPUTS_COLS = (
    "output_id",
    "run_id",
    "project_key",
    "source_package",
    "forecast_period",
    "basis_labels",
    "estimated_final_cost",
    "forecast_at_completion",
    "cost_to_complete",
    "variance_to_budget",
    "variance_to_prior_forecast",
    "source_path",
    "source_sha256",
    "raw_json",
    "created_utc",
    "updated_utc",
)
FORECAST_OUTPUT_BUDGET_CODES_COLS = (
    "id",
    "output_id",
    "project_key",
    "budget_code_key",
    "cost_code",
    "category",
    "forecast_action",
    "recommended_projected_cost",
    "recommended_cost_to_complete",
    "confidence",
    "source_row_number",
    "raw_json",
    "created_utc",
    "updated_utc",
)
FORECAST_OUTPUT_RISKS_COLS = (
    "id",
    "output_id",
    "project_key",
    "risk_id",
    "severity",
    "budget_code_key",
    "cost_code",
    "category",
    "risk_type",
    "source_row_number",
    "raw_json",
    "created_utc",
    "updated_utc",
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


def upsert_output(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_outputs", row, ("output_id",))


def upsert_output_budget_code(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_budget_codes", row, ("output_id", "budget_code_key"))


def upsert_output_risk(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_risks", row, ("output_id", "risk_id"))


# Maps the engine's planned-table keys to their per-row upsert helper.
_WRITERS = {
    "outputs": upsert_output,
    "budget_codes": upsert_output_budget_code,
    "risks": upsert_output_risk,
}


def apply_plan(
    conn: sqlite3.Connection, planned: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    """Upsert every planned row into the active v63 tables. Returns per-key written counts."""
    for key, writer in _WRITERS.items():
        for row in planned.get(key, []):
            writer(conn, row)
    return {key: len(planned.get(key, [])) for key in _WRITERS}


def _read_raw(
    conn: sqlite3.Connection,
    table: str,
    order_by: str,
    *,
    output_id: str,
) -> list[dict[str, Any]]:
    sql = f"SELECT raw_json FROM {table} WHERE output_id = ? ORDER BY {order_by}"
    return [json.loads(r[0]) for r in conn.execute(sql, (output_id,))]


def read_output_header_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """The projected run-output header row(s) for an output_id."""
    return _read_raw(conn, "forecast_outputs", "output_id", output_id=output_id)


def read_output_budget_codes_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Per-code recommendation rows in source-file order (source_row_number)."""
    return _read_raw(conn, "forecast_output_budget_codes", "source_row_number", output_id=output_id)


def read_output_risks_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Risk-register rows in source-file order (source_row_number)."""
    return _read_raw(conn, "forecast_output_risks", "source_row_number", output_id=output_id)
