"""Idempotent writers + DB-backed read repositories for the v63 run-output tables.

Writes are UPSERTs keyed on each table's UNIQUE/PRIMARY constraint (no new schema);
``created_utc`` and the conflict-key columns are never overwritten, so re-running an
apply is idempotent. Read repositories return the projected row's ``raw_json``
(``json.loads``) and nothing else, so a parity test can compare DB output against the
source package rows (canonical row-equivalence).

Coverage: the header (``forecast_outputs``), per-code recommendations
(``forecast_output_budget_codes``), risk register (``forecast_output_risks``), and — added in
Phase 2c — monthly / probability / changes / staffing. ``commitment_exposure`` and
``schedule_phasing`` remain empty (no clean per-row source yet).
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
# P8 explainability / audit-trail narratives. UNIQUE(output_id, scope, narrative_key).
FORECAST_OUTPUT_NARRATIVES_COLS = (
    "id",
    "output_id",
    "project_key",
    "scope",
    "narrative_key",
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


# Phase 2c coverage tables. These conflict on the deterministic PK ``id`` (derived from the
# natural key) rather than the table UNIQUE: it is robustly idempotent even where the UNIQUE
# includes a column the source never emits (e.g. staffing ``role`` is NULL).
def upsert_output_monthly(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_monthly", row, ("id",))


def upsert_output_probability(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_probability", row, ("id",))


def upsert_output_change(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_changes", row, ("id",))


def upsert_output_staffing(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_staffing", row, ("id",))


def upsert_output_commitment_exposure(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_commitment_exposure", row, ("id",))


def upsert_output_schedule_phasing(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_schedule_phasing", row, ("id",))


# P8: idempotent on the table UNIQUE (output_id, scope, narrative_key).
def upsert_output_narrative(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_narratives", row, ("output_id", "scope", "narrative_key"))


# v74 operator month-window matrix: per-budget-code table rows + the dense per-month total row.
# Idempotent on the table UNIQUE constraints (matches existing budget-code / header conventions).
def upsert_output_monthly_table_row(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_monthly_table_rows", row, ("output_id", "budget_code_key"))


def upsert_output_monthly_table_total(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_output_monthly_table_totals", row, ("output_id",))


# Maps the engine's planned-table keys to their per-row upsert helper.
_WRITERS = {
    "outputs": upsert_output,
    "budget_codes": upsert_output_budget_code,
    "risks": upsert_output_risk,
    "monthly": upsert_output_monthly,
    "probability": upsert_output_probability,
    "changes": upsert_output_change,
    "staffing": upsert_output_staffing,
    "commitment_exposure": upsert_output_commitment_exposure,
    "schedule_phasing": upsert_output_schedule_phasing,
    "narratives": upsert_output_narrative,
    "monthly_table_rows": upsert_output_monthly_table_row,
    "monthly_table_totals": upsert_output_monthly_table_total,
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


def read_output_monthly_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Monthly forecast rows in source-file order (source_row_number)."""
    return _read_raw(conn, "forecast_output_monthly", "source_row_number", output_id=output_id)


def read_output_probability_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Probability-band rows in source-file order (source_row_number)."""
    return _read_raw(conn, "forecast_output_probability", "source_row_number", output_id=output_id)


def read_output_changes_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Change/delta rows in source-file order (source_row_number)."""
    return _read_raw(conn, "forecast_output_changes", "source_row_number", output_id=output_id)


def read_output_staffing_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Staffing rows in source-file order (source_row_number)."""
    return _read_raw(conn, "forecast_output_staffing", "source_row_number", output_id=output_id)


def read_output_commitment_exposure_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Commitment-exposure rows in source-file order (source_row_number)."""
    return _read_raw(
        conn, "forecast_output_commitment_exposure", "source_row_number", output_id=output_id
    )


def read_output_schedule_phasing_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """Schedule-phasing rows in source-file order (source_row_number)."""
    return _read_raw(
        conn, "forecast_output_schedule_phasing", "source_row_number", output_id=output_id
    )


def read_output_narratives_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """P8 explainability/audit narrative rows in build order (source_row_number)."""
    return _read_raw(conn, "forecast_output_narratives", "source_row_number", output_id=output_id)


def _read_columns(
    conn: sqlite3.Connection, table: str, order_by: str, *, output_id: str
) -> list[dict[str, Any]]:
    """Read full column rows (for the v74 matrix tables, which carry no raw_json)."""
    prior = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            f"SELECT * FROM {table} WHERE output_id = ? ORDER BY {order_by}", (output_id,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.row_factory = prior


def read_output_monthly_table_rows_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> list[dict[str, Any]]:
    """v74 per-budget-code matrix rows, ordered by sort_key (budget_code_key)."""
    return _read_columns(conn, "forecast_output_monthly_table_rows", "sort_key", output_id=output_id)


def read_output_monthly_table_totals_from_db(
    conn: sqlite3.Connection, *, output_id: str
) -> dict[str, Any] | None:
    """v74 dense per-month total row for an output (one row), or None."""
    rows = _read_columns(conn, "forecast_output_monthly_table_totals", "output_id", output_id=output_id)
    return rows[0] if rows else None
