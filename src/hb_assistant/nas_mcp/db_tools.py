"""Structured read-only DB access for NAS MCP."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from hb_assistant.config.db_storage_guard import assert_db_storage_allowed

from .config import NasMcpConfig
from .db_allowlist import (
    get_table_spec,
    validate_columns,
    validate_filter_columns,
    validate_order_by,
)

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DbSelectError(Exception):
    """Denied or invalid structured DB select."""


def _ro_uri(db_path: str) -> str:
    assert_db_storage_allowed(db_path, context="nas_mcp_db_select")
    return f"file:{db_path}?mode=ro"


def hb_db_select(
    *,
    config: NasMcpConfig,
    table_key: str,
    columns: list[str],
    filters: dict[str, Any] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    spec = get_table_spec(table_key)
    validate_columns(spec, columns)
    filters = filters or {}
    validate_filter_columns(spec, filters)
    validate_order_by(spec, order_by)
    for name in [spec.table_name, *columns, *filters.keys(), order_by or ""]:
        if name and not _IDENT.match(name):
            raise DbSelectError("invalid identifier")

    requested_limit = limit if limit is not None else config.default_db_rows
    applied_limit = min(max(1, int(requested_limit)), config.max_db_rows)

    select_cols = ", ".join(columns)
    sql = f"SELECT {select_cols} FROM {spec.table_name}"
    params: list[Any] = []
    if filters:
        clauses = [f"{col} = ?" for col in filters]
        sql += " WHERE " + " AND ".join(clauses)
        params.extend(filters[col] for col in filters)
    if order_by:
        sql += f" ORDER BY {order_by}"
    sql += " LIMIT ?"
    params.append(applied_limit)

    conn = sqlite3.connect(_ro_uri(str(config.db_path)), uri=True, timeout=5.0)
    try:
        conn.execute("PRAGMA query_only=ON")
        cur = conn.execute(sql, params)
        rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
    finally:
        conn.close()

    payload = {
        "table_key": table_key,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "limit_requested": requested_limit,
        "limit_applied": applied_limit,
    }
    encoded = json.dumps(payload, default=str).encode("utf-8")
    if len(encoded) > config.max_response_bytes:
        raise DbSelectError("response byte limit exceeded")
    return payload
