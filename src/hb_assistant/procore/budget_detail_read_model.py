"""Budget Detail Rows endpoint-specific read model.

This module projects full local raw landing rows into queryable Budget Detail
Rows tables. It never calls Procore and never emits raw payload bodies in
receipts; live transport is handled by ``live_sync`` before this projector runs.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from hb_assistant.store.connection import open_connection, transaction

from .structured_analytics import _rank

TARGET_CODE = "1000.15-01-426.MAT"
SOURCE_QUALITY_LIVE_FULL = "live_full_payload"

ROW_TABLE = "procore_ep_budget_detail_rows"
CELL_TABLE = "procore_ep_budget_detail_row_cells"
COLUMN_TABLE = "procore_ep_budget_detail_columns"
RAW_TABLE = "procore_endpoint_raw_payloads"

COMMON_AMOUNT_FIELDS = (
    "original_budget_amount",
    "revised_budget",
    "approved_change_orders",
    "pending_budget_changes",
    "projected_budget",
    "committed_costs",
    "direct_costs",
    "erp_direct_costs",
    "actual_cost",
    "job_to_date_costs",
    "projected_costs",
    "forecast_to_complete",
    "estimated_cost_at_completion",
    "projected_over_under",
    "erp_job_to_date_costs",
)

_MONEYISH_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_BUDGET_KEY_RE = re.compile(r"^[^.]+\.[^.]+\.[^.]+$")
_NON_ALIAS_CHARS_RE = re.compile(r"[^a-z0-9]+")
_DIRECT_AMOUNT_ALIASES: dict[str, tuple[str, ...]] = {
    "original_budget_amount": ("original_budget",),
    "approved_change_orders": ("approved_cos", "approved_change_orders_amount"),
    "pending_budget_changes": ("pending_budget_change", "pending_budget_changes_amount"),
    "erp_direct_costs": ("erp_direct_cost", "erp_direct_costs_amount"),
    "erp_job_to_date_costs": (
        "erp_job_to_date_cost",
        "erp_jtd_costs",
        "erp_jtd_cost",
    ),
    "job_to_date_costs": ("job_to_date_cost", "jtd_costs", "jtd_cost"),
    "forecast_to_complete": (
        "projected_cost_to_complete",
        "projected_costs_to_complete",
        "cost_to_complete",
    ),
    "estimated_cost_at_completion": ("estimated_cost_at_completion_amount",),
    "projected_over_under": (
        "projected_over_under_amount",
        "projected_over_under_budget",
    ),
}
# ``actual_cost`` intentionally has no aliases here. Current copied-DB evidence
# has no literal Actual Cost source; Direct/JTD/ERP values are distinct concepts.
_CELL_AMOUNT_ALIASES: dict[str, str] = {
    "revisedbudget": "revised_budget",
    "projectedbudget": "projected_budget",
    "committedcosts": "committed_costs",
    "directcosts": "direct_costs",
    "erpdirectcosts": "erp_direct_costs",
    "erpjobtodatecosts": "erp_job_to_date_costs",
    "erpjtdcosts": "erp_job_to_date_costs",
    "jobtodatecosts": "job_to_date_costs",
    "jtdcosts": "job_to_date_costs",
    "projectedcosts": "projected_costs",
    "projectedcosttocomplete": "forecast_to_complete",
    "costtocomplete": "forecast_to_complete",
    "estimatedcostatcompletion": "estimated_cost_at_completion",
    "projectedoverunder": "projected_over_under",
    "pendingbudgetchanges": "pending_budget_changes",
    "approvedcos": "approved_change_orders",
    "approvedchangeorders": "approved_change_orders",
}


@dataclass(frozen=True)
class ProjectionReceipt:
    inspected_raw_rows: int
    row_rows_written: int
    cell_rows_written: int
    column_rows_written: int
    skipped_missing_record_id: int
    skipped_lower_quality: int
    degraded_parse_errors: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "inspected_raw_rows": self.inspected_raw_rows,
            "structured_budget_detail_row_rows_inserted_or_updated": self.row_rows_written,
            "budget_detail_cell_rows_inserted_or_updated": self.cell_rows_written,
            "structured_budget_detail_column_rows_inserted_or_updated": self.column_rows_written,
            "skipped_missing_record_id": self.skipped_missing_record_id,
            "skipped_lower_quality": self.skipped_lower_quality,
            "degraded_parse_errors": self.degraded_parse_errors,
            "raw_payload_body_emitted": False,
            "external_writeback_performed": 0,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8", "replace")).hexdigest()


def _key(prefix: str, *parts: Any) -> str:
    joined = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}-{_hash(joined)[:32]}"


def _loads(payload_json: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _scalar(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("flat_code", "code", "name", "label", "display_name", "id"):
            if value.get(key) not in (None, ""):
                return str(value[key])
        return None
    return None


def _path(payload: dict[str, Any], *paths: str) -> Any:
    for dotted in paths:
        cur: Any = payload
        ok = True
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                ok = False
                break
            cur = cur[part]
        if ok and cur not in (None, ""):
            return cur
    return None


def _amount(payload: dict[str, Any], field: str) -> str | None:
    for path in (field, *_DIRECT_AMOUNT_ALIASES.get(field, ())):
        value = _decimal_text(_scalar(_path(payload, path)))
        if value is not None:
            return value
    return None


def _decimal_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.replace(",", "").strip()
    if not _MONEYISH_RE.match(stripped):
        return None
    try:
        return str(Decimal(stripped))
    except (InvalidOperation, ValueError):
        return None


def _normalize_amount_label(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("&", "and")
    normalized = _NON_ALIAS_CHARS_RE.sub("", normalized)
    return normalized or None


def _normalize_field_identity(value: str | None) -> str | None:
    if not value:
        return None
    terminal = _terminal_field_path(value)
    normalized = re.sub(r"[^a-z0-9]+", "_", terminal.strip().lower()).strip("_")
    return normalized or None


def _terminal_field_path(path: str | None) -> str | None:
    if not path:
        return None
    terminal = path.rsplit(".", 1)[-1]
    if "]" in terminal:
        terminal = terminal.rsplit("]", 1)[-1] or terminal
    return terminal.strip("$[]") or terminal


def _promoted_amount_field(cell: dict[str, Any]) -> str | None:
    candidates = (
        cell.get("column_label"),
        cell.get("column_name"),
        cell.get("column_key"),
        _terminal_field_path(cell.get("field_path")),
    )
    for candidate in candidates:
        field = _CELL_AMOUNT_ALIASES.get(_normalize_amount_label(candidate))
        if field:
            return field
    return None


def _currency(payload: dict[str, Any]) -> str | None:
    return _scalar(
        _path(
            payload,
            "currency_iso_code",
            "currency_code",
            "currency_configuration.currency_iso_code",
        )
    )


def _budget_view_id(payload: dict[str, Any], parent_record_id: Any) -> str | None:
    return _scalar(
        _path(payload, "budget_view_id", "budget_view.id", "view_id")
    ) or _scalar(parent_record_id)


def _wbs_flat_code(payload: dict[str, Any]) -> str | None:
    return _scalar(_path(payload, "wbs_code.flat_code", "wbs_flat_code", "budget_code"))


def _canonical_budget_code_key(payload: dict[str, Any]) -> str | None:
    for value in (
        _wbs_flat_code(payload),
        _scalar(_path(payload, "canonical_budget_code_key")),
        _scalar(_path(payload, "budget_code")),
    ):
        if value and _BUDGET_KEY_RE.match(value):
            return value
    return None


def _cost_code(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    cost = _path(payload, "cost_code")
    if isinstance(cost, dict):
        return _scalar(cost.get("id")), _scalar(cost.get("full_code") or cost.get("code"))
    return _scalar(_path(payload, "cost_code_id")), _scalar(cost)


def _cost_type(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    cost_type = _path(payload, "cost_type", "line_item_type")
    if isinstance(cost_type, dict):
        return _scalar(cost_type.get("id")), _scalar(
            cost_type.get("abbreviation") or cost_type.get("code") or cost_type.get("name")
        )
    return _scalar(_path(payload, "cost_type_id", "line_item_type_id")), _scalar(cost_type)


def _category(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    # Budget Detail exposes category/category_id as source fields. They are not
    # compatibility aliases for cost_type/cost_type_id.
    return _scalar(_path(payload, "category_id")), _scalar(_path(payload, "category"))


def _record_id(endpoint_key: str, payload: dict[str, Any], row: sqlite3.Row) -> str | None:
    value = _scalar(_path(payload, "id"))
    if value:
        return value
    try:
        row_value = row["record_id"]
    except (IndexError, KeyError):
        row_value = None
    return _scalar(row_value)


def _iter_scalar_leaves(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            yield from _iter_scalar_leaves(value[key], f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _iter_scalar_leaves(item, f"{path}[{idx}]")
    elif value is not None:
        yield path, value


def _column_lookup(conn: sqlite3.Connection, project_key: str | None) -> dict[str, dict[str, str | None]]:
    try:
        rows = conn.execute(
            """
            SELECT budget_view_id, column_id, column_key, name, label, field_path
            FROM procore_ep_budget_detail_columns
            WHERE (? IS NULL OR project_key = ?)
            """,
            (project_key, project_key),
        ).fetchall()
    except sqlite3.Error:
        return {}
    out: dict[str, dict[str, str | None]] = {}
    for row in rows:
        for key in (row["field_path"], row["name"], row["column_key"], row["column_id"]):
            if key:
                out[f"{row['budget_view_id'] or ''}|{key}"] = dict(row)
                out[f"|{key}"] = dict(row)
    return out


def _existing_rank(conn: sqlite3.Connection, table: str, key_column: str, key_value: str) -> int:
    try:
        row = conn.execute(
            f"SELECT source_quality FROM {table} WHERE {key_column} = ?", (key_value,)
        ).fetchone()
    except sqlite3.Error:
        return 0
    return _rank(row[0]) if row else 0


def _upsert(conn: sqlite3.Connection, table: str, values: dict[str, Any], key_column: str) -> None:
    cols = list(values)
    placeholders = ", ".join("?" for _ in cols)
    assignments = ", ".join(
        f"{col}=excluded.{col}" for col in cols if col not in {key_column, "created_utc"}
    )
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({key_column}) DO UPDATE SET {assignments}",
        tuple(values[col] for col in cols),
    )


def _base_values(row: sqlite3.Row, *, record_id: str, parent_id: str | None, now_utc: str) -> dict[str, Any]:
    return {
        "raw_payload_id": row["raw_payload_id"],
        "endpoint_key": row["endpoint_key"],
        "endpoint_family": row["endpoint_family"],
        "project_key": row["project_key"],
        "project_id": row["project_id"],
        "project_id_hash": row["project_id_hash"],
        "company_id": row["company_id"],
        "company_id_hash": row["company_id_hash"],
        "record_id": record_id,
        "record_id_hash": _hash(record_id),
        "parent_record_id": parent_id,
        "parent_record_id_hash": _hash(parent_id) if parent_id else None,
        "payload_hash": row["payload_hash"],
        "source_quality": row["source_quality"],
        "payload_seen_first_utc": row["payload_seen_first_utc"],
        "payload_seen_last_utc": row["payload_seen_last_utc"],
        "is_current": 1,
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def _project_column(conn: sqlite3.Connection, row: sqlite3.Row, payload: dict[str, Any], now_utc: str) -> int:
    record_id = _record_id("budget-detail-columns", payload, row)
    if not record_id:
        return 0
    parent_id = _scalar(row["parent_record_id"]) or _budget_view_id(payload, None)
    record_key = _key("pbdc", row["project_key"], parent_id, record_id)
    if _existing_rank(conn, COLUMN_TABLE, "record_key", record_key) > _rank(row["source_quality"]):
        return 0
    name = _scalar(_path(payload, "name"))
    label = _scalar(_path(payload, "label", "localized_name", "display_name")) or name
    values = {
        "record_key": record_key,
        **_base_values(row, record_id=record_id, parent_id=parent_id, now_utc=now_utc),
        "budget_view_id": parent_id,
        "column_id": record_id,
        "column_key": _scalar(_path(payload, "key", "slug")) or name or record_id,
        "name": name,
        "label": label,
        "data_type": _scalar(_path(payload, "type", "data_type")),
        "field_path": _scalar(_path(payload, "field_path", "path")) or name,
        "position": _scalar(_path(payload, "position")),
        "visible": _scalar(_path(payload, "visible")),
        "payload_sidecar_json": json.dumps(
            {
                key: value
                for key, value in payload.items()
                if key not in {"id", "name", "label", "localized_name", "display_name", "type", "data_type", "position", "visible"}
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    }
    _upsert(conn, COLUMN_TABLE, values, "record_key")
    return 1


def _project_row(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    payload: dict[str, Any],
    now_utc: str,
    columns: dict[str, dict[str, str | None]],
) -> tuple[int, int, bool]:
    record_id = _record_id("budget-detail-rows", payload, row)
    if not record_id:
        return 0, 0, False
    parent_id = _scalar(row["parent_record_id"]) or _budget_view_id(payload, None)
    record_key = _key("pbdr", row["project_key"], parent_id, record_id)
    if _existing_rank(conn, ROW_TABLE, "record_key", record_key) > _rank(row["source_quality"]):
        return 0, 0, True

    cost_code_id, cost_code = _cost_code(payload)
    cost_type_id, cost_type = _cost_type(payload)
    category_id, category = _category(payload)
    wbs_id = _scalar(_path(payload, "wbs_code.id", "wbs_code_id"))
    wbs_flat = _wbs_flat_code(payload)
    canonical = _canonical_budget_code_key(payload)
    budget_row_id = _scalar(_path(payload, "budget_row_id")) or record_id
    common_amounts = {field: _amount(payload, field) for field in COMMON_AMOUNT_FIELDS}
    currency = _currency(payload)
    cells_to_write: list[dict[str, Any]] = []
    for field_path, raw_value in _iter_scalar_leaves(payload):
        value_text = _scalar(raw_value)
        if value_text is None:
            continue
        short_name = field_path.rsplit(".", 1)[-1]
        col = (
            columns.get(f"{parent_id or ''}|{field_path}")
            or columns.get(f"{parent_id or ''}|{short_name}")
            or columns.get(f"|{field_path}")
            or columns.get(f"|{short_name}")
            or {}
        )
        value_decimal_text = _decimal_text(value_text)
        cell = {
            "cell_key": _key("pbdcell", record_key, field_path),
            "record_key": record_key,
            "raw_payload_id": row["raw_payload_id"],
            "endpoint_key": row["endpoint_key"],
            "endpoint_family": row["endpoint_family"],
            "project_key": row["project_key"],
            "project_id": row["project_id"],
            "project_id_hash": row["project_id_hash"],
            "company_id": row["company_id"],
            "company_id_hash": row["company_id_hash"],
            "budget_view_id": parent_id,
            "budget_row_id": budget_row_id,
            "row_id": record_id,
            "column_id": col.get("column_id"),
            "column_key": col.get("column_key"),
            "column_name": col.get("name") or short_name,
            "column_label": col.get("label") or col.get("name") or short_name,
            "field_path": field_path,
            "value_text": value_text,
            "value_decimal_text": value_decimal_text,
            "currency_iso_code": currency,
            "value_json": json.dumps(raw_value, sort_keys=True, separators=(",", ":")),
            "payload_hash": row["payload_hash"],
            "source_quality": row["source_quality"],
            "is_current": 1,
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
        promoted_field = _promoted_amount_field(cell)
        if promoted_field and value_decimal_text is not None and not common_amounts.get(promoted_field):
            common_amounts[promoted_field] = value_decimal_text
        if category is None or category_id is None:
            exact_fields = {
                _normalize_field_identity(field_path),
                _normalize_field_identity(cell["column_key"]),
                _normalize_field_identity(cell["column_name"]),
                _normalize_field_identity(cell["column_label"]),
            }
            if category is None and "category" in exact_fields:
                category = value_text
            if category_id is None and "category_id" in exact_fields:
                category_id = value_text
        cells_to_write.append(cell)
    sidecar_keys = {
        "id",
        "budget_view_id",
        "budget_view",
        "wbs_code",
        "wbs_code_id",
        "wbs_flat_code",
        "budget_code",
        "cost_code",
        "cost_code_id",
        "cost_type",
        "cost_type_id",
        "category",
        "category_id",
        "line_item_type",
        "line_item_type_id",
        "description",
        *COMMON_AMOUNT_FIELDS,
    }
    values = {
        "record_key": record_key,
        **_base_values(row, record_id=record_id, parent_id=parent_id, now_utc=now_utc),
        "budget_view_id": parent_id,
        "budget_row_id": budget_row_id,
        "row_id": record_id,
        "wbs_code_id": wbs_id,
        "wbs_flat_code": wbs_flat,
        "budget_code": _scalar(_path(payload, "budget_code")) or wbs_flat,
        "canonical_budget_code_key": canonical,
        "cost_code_id": cost_code_id,
        "cost_code": cost_code,
        "cost_type_id": cost_type_id,
        "cost_type": cost_type,
        "category": category,
        "category_id": category_id,
        "category_id_hash": _hash(category_id) if category_id else None,
        "line_item_type_id": _scalar(_path(payload, "line_item_type_id")),
        "description": _scalar(_path(payload, "description", "wbs_code.description")),
        **common_amounts,
        "payload_sidecar_json": json.dumps(
            {key: value for key, value in payload.items() if key not in sidecar_keys},
            sort_keys=True,
            separators=(",", ":"),
        ),
    }
    _upsert(conn, ROW_TABLE, values, "record_key")

    conn.execute(f"DELETE FROM {CELL_TABLE} WHERE record_key = ?", (record_key,))
    cells = 0
    for cell in cells_to_write:
        _upsert(conn, CELL_TABLE, cell, "cell_key")
        cells += 1
    return 1, cells, False


def project_budget_detail_read_model(
    *,
    db_path: str | Path | None = None,
    project_key: str | None = None,
    budget_view_ids: list[str] | None = None,
    require_live_full: bool = True,
    apply: bool = False,
) -> dict[str, Any]:
    """Project raw Budget Detail payloads into endpoint-specific read-model tables."""
    with open_connection(Path(db_path) if db_path is not None else None) as conn:
        return _project_with_conn(
            conn,
            project_key=project_key,
            budget_view_ids=budget_view_ids,
            require_live_full=require_live_full,
            apply=apply,
        )


def _project_with_conn(
    conn: sqlite3.Connection,
    *,
    project_key: str | None,
    budget_view_ids: list[str] | None,
    require_live_full: bool,
    apply: bool,
) -> dict[str, Any]:
    clauses = ["endpoint_key IN ('budget-detail-columns', 'budget-detail-rows')", "is_current = 1"]
    params: list[Any] = []
    if project_key:
        clauses.append("project_key = ?")
        params.append(project_key)
    if require_live_full:
        clauses.append("source_quality = ?")
        params.append(SOURCE_QUALITY_LIVE_FULL)
        clauses.append("raw_procore_payload_persisted = 1")
        clauses.append("redaction_status = 'full_business_payload'")
        clauses.append("security_scrub_status = 'transport_secrets_removed'")
    if budget_view_ids:
        placeholders = ", ".join("?" for _ in budget_view_ids)
        clauses.append(f"parent_record_id IN ({placeholders})")
        params.extend(budget_view_ids)
    sql = (
        "SELECT * FROM procore_endpoint_raw_payloads "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY endpoint_key, project_key, parent_record_id, record_id, raw_payload_id"
    )
    try:
        rows = list(conn.execute(sql, tuple(params)))
    except sqlite3.Error as exc:
        return {
            "ok": False,
            "status": "schema_unavailable",
            "error_kind": type(exc).__name__,
            "local_db_write_performed": False,
            "external_writeback_performed": 0,
        }

    receipt = ProjectionReceipt(0, 0, 0, 0, 0, 0, 0)
    counters = receipt.__dict__.copy()
    now_utc = _now()

    def _run(active: sqlite3.Connection) -> None:
        nonlocal counters
        for row in rows:
            counters["inspected_raw_rows"] += 1
            payload = _loads(row["payload_json"])
            if payload is None:
                counters["degraded_parse_errors"] += 1
                continue
            if row["endpoint_key"] == "budget-detail-columns":
                written = _project_column(active, row, payload, now_utc)
                counters["column_rows_written"] += written
                if written == 0 and not _record_id("budget-detail-columns", payload, row):
                    counters["skipped_missing_record_id"] += 1
        columns = _column_lookup(active, project_key)
        for row in rows:
            if row["endpoint_key"] != "budget-detail-rows":
                continue
            payload = _loads(row["payload_json"])
            if payload is None:
                counters["degraded_parse_errors"] += 1
                continue
            row_written, cell_written, skipped_lower = _project_row(
                active, row, payload, now_utc, columns
            )
            counters["row_rows_written"] += row_written
            counters["cell_rows_written"] += cell_written
            if skipped_lower:
                counters["skipped_lower_quality"] += 1
            if row_written == 0 and not _record_id("budget-detail-rows", payload, row):
                counters["skipped_missing_record_id"] += 1

    if apply:
        with transaction(conn):
            _run(conn)
    else:
        counters["inspected_raw_rows"] = len(rows)

    out = ProjectionReceipt(**counters).as_dict()
    out.update(
        {
            "ok": counters["degraded_parse_errors"] == 0,
            "status": "success" if counters["degraded_parse_errors"] == 0 else "partial",
            "mode": "apply" if apply else "dry_run",
            "local_db_write_performed": bool(apply),
        }
    )
    return out


def target_code_summary(
    *,
    db_path: str | Path | None = None,
    project_key: str,
    target_code: str = TARGET_CODE,
) -> dict[str, Any]:
    """Return body-free availability summary for one canonical code."""
    with open_connection(Path(db_path) if db_path is not None else None) as conn:
        rows = conn.execute(
            f"""
            SELECT record_key, raw_payload_id, budget_view_id, payload_hash, source_quality,
                   payload_seen_first_utc, payload_seen_last_utc,
                   original_budget_amount, revised_budget, projected_budget, committed_costs,
                   direct_costs, erp_direct_costs, actual_cost, job_to_date_costs,
                   projected_costs, erp_job_to_date_costs, forecast_to_complete,
                   estimated_cost_at_completion, projected_over_under,
                   pending_budget_changes, approved_change_orders
            FROM {ROW_TABLE}
            WHERE project_key = ?
              AND (canonical_budget_code_key = ? OR wbs_flat_code = ?)
            ORDER BY budget_view_id, record_key
            """,
            (project_key, target_code, target_code),
        ).fetchall()
        view_ids = [row["budget_view_id"] for row in rows if row["budget_view_id"]]
        cell_count = 0
        field_names: set[str] = set()
        if rows:
            keys = [row["record_key"] for row in rows]
            placeholders = ", ".join("?" for _ in keys)
            cell_rows = conn.execute(
                f"""
                SELECT column_name, field_path
                FROM {CELL_TABLE}
                WHERE record_key IN ({placeholders})
                """,
                tuple(keys),
            ).fetchall()
            cell_count = len(cell_rows)
            field_names = {
                (row["column_name"] or row["field_path"] or "")
                for row in cell_rows
                if row["column_name"] or row["field_path"]
            }
        amount_presence = {
            field: sum(1 for row in rows if row[field] not in (None, ""))
            for field in (
                "original_budget_amount",
                "revised_budget",
                "projected_budget",
                "committed_costs",
                "direct_costs",
                "erp_direct_costs",
                "actual_cost",
                "job_to_date_costs",
                "projected_costs",
                "erp_job_to_date_costs",
                "forecast_to_complete",
                "estimated_cost_at_completion",
                "projected_over_under",
                "pending_budget_changes",
                "approved_change_orders",
            )
        }
        return {
            "project_key": project_key,
            "target_code": target_code,
            "queryable": bool(rows),
            "row_count": len(rows),
            "budget_view_ids": sorted(set(view_ids)),
            "raw_payload_ids": sorted({row["raw_payload_id"] for row in rows if row["raw_payload_id"]}),
            "payload_hashes": sorted({row["payload_hash"] for row in rows if row["payload_hash"]}),
            "source_qualities": sorted({row["source_quality"] for row in rows if row["source_quality"]}),
            "seen_first_utc_min": min((row["payload_seen_first_utc"] for row in rows if row["payload_seen_first_utc"]), default=None),
            "seen_last_utc_max": max((row["payload_seen_last_utc"] for row in rows if row["payload_seen_last_utc"]), default=None),
            "amount_field_presence": amount_presence,
            "dynamic_cell_count": cell_count,
            "dynamic_cell_field_names_sample": sorted(field_names)[:50],
            "raw_payload_body_emitted": False,
        }


__all__ = [
    "COMMON_AMOUNT_FIELDS",
    "SOURCE_QUALITY_LIVE_FULL",
    "TARGET_CODE",
    "project_budget_detail_read_model",
    "target_code_summary",
]
