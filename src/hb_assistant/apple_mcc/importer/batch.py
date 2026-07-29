"""Batch import orchestration (BEGIN IMMEDIATE)."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable

from hb_assistant.apple_mcc.importer.validate import ValidationError, validate_item


def begin_immediate(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")


def import_batch(
    conn: sqlite3.Connection,
    items: list[dict[str, Any]],
    *,
    import_one: Callable[[sqlite3.Connection, dict[str, Any]], None],
) -> dict[str, int]:
    accepted = 0
    rejected = 0
    begin_immediate(conn)
    try:
        for item in items:
            try:
                validate_item(item)
                import_one(conn, item)
                accepted += 1
            except (ValidationError, sqlite3.IntegrityError, ValueError):
                rejected += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"accepted": accepted, "rejected": rejected}
