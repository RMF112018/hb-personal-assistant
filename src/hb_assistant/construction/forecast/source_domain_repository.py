"""Idempotent writers + DB-backed read repositories for the three v59 source tables.

Writes are UPSERTs keyed on each table's PRIMARY KEY / UNIQUE constraint (no new
schema). ``created_utc`` and the conflict-key columns are never overwritten, so
re-running ``apply`` is idempotent.

Read repositories return the exact original JSONL row (``json.loads(raw_json)``)
and NOTHING else — no lineage/index columns are merged into the returned dicts —
so a parity test can compare DB output against the source JSONL byte-for-shape.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

# Insert-order columns per v59 table (must match migrator.py V59_STATEMENTS).
FORECAST_BUDGET_DETAILS_COLS = (
    "project_key",
    "budget_code_key",
    "source_package",
    "cost_code",
    "category",
    "source_path",
    "source_sha256",
    "source_row_number",
    "run_id",
    "raw_json",
    "created_utc",
    "updated_utc",
)
FORECAST_COST_ENTRIES_COLS = (
    "cost_entry_id",
    "project_key",
    "source_package",
    "source_row_number",
    "budget_code_key",
    "accounting_month",
    "source_path",
    "source_sha256",
    "run_id",
    "raw_json",
    "created_utc",
    "updated_utc",
)
FORECAST_MONTHLY_ACTUALS_COLS = (
    "project_key",
    "budget_code_key",
    "month",
    "type",
    "source_package",
    "amount",
    "entry_count",
    "source_path",
    "source_sha256",
    "source_row_number",
    "run_id",
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


def upsert_budget_detail(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(
        conn, "forecast_budget_details", row, ("project_key", "budget_code_key", "source_package")
    )


def upsert_cost_entry(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    # cost_entry_id is derived from (project_key|source_package|source_row_number), consistent
    # with the UNIQUE(project_key, source_package, source_row_number) constraint.
    _upsert(conn, "forecast_cost_entries", row, ("cost_entry_id",))


def upsert_monthly_actual(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(
        conn,
        "forecast_monthly_actuals_by_budget_code",
        row,
        ("project_key", "budget_code_key", "month", "type", "source_package"),
    )


# Maps the engine's planned-table keys to their per-row upsert helper.
_WRITERS = {
    "budget_details": upsert_budget_detail,
    "cost_entries": upsert_cost_entry,
    "monthly_actuals": upsert_monthly_actual,
}


def apply_plan(
    conn: sqlite3.Connection, planned: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    """Upsert every planned row into the three v59 tables. Returns per-table written counts."""
    for key, writer in _WRITERS.items():
        for row in planned.get(key, []):
            writer(conn, row)
    return {key: len(planned.get(key, [])) for key in _WRITERS}


def _read_raw(
    conn: sqlite3.Connection,
    table: str,
    order_by: str,
    *,
    project_key: str,
    source_package: str | None,
) -> list[dict[str, Any]]:
    sql = f"SELECT raw_json FROM {table} WHERE project_key = ?"
    params: list[Any] = [project_key]
    if source_package is not None:
        sql += " AND source_package = ?"
        params.append(source_package)
    sql += f" ORDER BY {order_by}"
    return [json.loads(r[0]) for r in conn.execute(sql, params)]


def read_budget_details_from_db(
    conn: sqlite3.Connection, *, project_key: str, source_package: str | None = None
) -> list[dict[str, Any]]:
    """Original BudgetDetails JSONL rows, ordered by budget_code_key (parity shape)."""
    return _read_raw(
        conn,
        "forecast_budget_details",
        "budget_code_key",
        project_key=project_key,
        source_package=source_package,
    )


def read_cost_entries_from_db(
    conn: sqlite3.Connection, *, project_key: str, source_package: str | None = None
) -> list[dict[str, Any]]:
    """Original CostEntries JSONL rows, ordered by source_row_number (parity shape)."""
    return _read_raw(
        conn,
        "forecast_cost_entries",
        "source_row_number",
        project_key=project_key,
        source_package=source_package,
    )


def read_monthly_actuals_from_db(
    conn: sqlite3.Connection, *, project_key: str, source_package: str | None = None
) -> list[dict[str, Any]]:
    """Original monthly-actuals JSONL rows, ordered by (budget_code_key, month, type)."""
    return _read_raw(
        conn,
        "forecast_monthly_actuals_by_budget_code",
        "budget_code_key, month, type",
        project_key=project_key,
        source_package=source_package,
    )


# --- file-order readers -----------------------------------------------------------------
# Ordered by source_row_number (1-based JSONL line index, unique per package/table = exact
# file order). These are drop-in replacements for ``list(read_jsonl(path))``: a consumer that
# expects rows in source-file order (e.g. the CFR context generator's Phase 4 read adapter)
# gets the same sequence the file-backed reader would yield. The business-key readers above
# are unchanged.


def read_budget_details_in_file_order(
    conn: sqlite3.Connection, *, project_key: str, source_package: str | None = None
) -> list[dict[str, Any]]:
    """Original BudgetDetails JSONL rows in source-file order (source_row_number)."""
    return _read_raw(
        conn,
        "forecast_budget_details",
        "source_row_number",
        project_key=project_key,
        source_package=source_package,
    )


def read_cost_entries_in_file_order(
    conn: sqlite3.Connection, *, project_key: str, source_package: str | None = None
) -> list[dict[str, Any]]:
    """Original CostEntries JSONL rows in source-file order (source_row_number)."""
    return _read_raw(
        conn,
        "forecast_cost_entries",
        "source_row_number",
        project_key=project_key,
        source_package=source_package,
    )


def read_monthly_actuals_in_file_order(
    conn: sqlite3.Connection, *, project_key: str, source_package: str | None = None
) -> list[dict[str, Any]]:
    """Original monthly-actuals JSONL rows in source-file order (source_row_number)."""
    return _read_raw(
        conn,
        "forecast_monthly_actuals_by_budget_code",
        "source_row_number",
        project_key=project_key,
        source_package=source_package,
    )
