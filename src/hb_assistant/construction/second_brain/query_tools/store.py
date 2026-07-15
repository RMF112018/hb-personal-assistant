"""Phase 08A query-tool receipt store (Prompt 06).

Writes a metadata-only audit row into the V26 ``query_tool_receipts`` table for one
query-tool call. The table enforces ``CHECK(arbitrary_sql_allowed = 0)`` and
``CHECK(external_writeback_performed = 0)`` at the DB layer; this writer leaves both
at 0 and persists only counts, status, and the tool name — never rows, excerpts, or
any raw content. Mirrors ``second_brain/store.py::write_config_receipt``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import ensure_schema_ready

if TYPE_CHECKING:
    from .models import QueryToolResult


def write_query_tool_receipt(
    *,
    result: QueryToolResult,
    retrieval_receipt_id: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one query-tool receipt; returns the generated ``tool_receipt_id``.

    Local-only, additive, metadata-only. Guard columns stay at 0 via DB CHECKs.
    """
    ensure_schema_ready(db_path)  # ensure V26 table exists (idempotent)

    receipt_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO query_tool_receipts
                (tool_receipt_id, retrieval_receipt_id, tool_name, project_key,
                 row_count, char_count, truncated, status, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                retrieval_receipt_id,
                result.tool_name,
                result.project_key,
                result.row_count,
                result.char_count,
                1 if result.truncated else 0,
                result.status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return receipt_id


def read_latest_query_tool_receipts(
    *, db_path: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent query-tool receipt rows (metadata only)."""
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT tool_receipt_id, retrieval_receipt_id, tool_name, project_key,
               row_count, char_count, truncated, status, created_utc
        FROM query_tool_receipts
        ORDER BY created_utc DESC, tool_receipt_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]
