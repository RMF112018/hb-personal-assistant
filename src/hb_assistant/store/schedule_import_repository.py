"""Repository for schedule_file_imports rows."""

from __future__ import annotations

import sqlite3
from typing import Any

from .connection import get_connection, open_connection, transaction


class ScheduleImportRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self._db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def insert_import(self, row: dict[str, Any], *, conn: sqlite3.Connection | None = None) -> None:
        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        names = ", ".join(cols)
        if conn is not None:
            conn.execute(
                f"INSERT INTO schedule_file_imports ({names}) VALUES ({placeholders})",
                tuple(row[c] for c in cols),
            )
            return
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    f"INSERT INTO schedule_file_imports ({names}) VALUES ({placeholders})",
                    tuple(row[c] for c in cols),
                )

    def update_import(
        self,
        import_id: str,
        updates: dict[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if not updates:
            return
        sets = ", ".join(f"{k}=?" for k in updates)
        if conn is not None:
            conn.execute(
                f"UPDATE schedule_file_imports SET {sets} WHERE import_id=?",
                (*updates.values(), import_id),
            )
            return
        with open_connection(self._db_path) as active:
            with transaction(active):
                active.execute(
                    f"UPDATE schedule_file_imports SET {sets} WHERE import_id=?",
                    (*updates.values(), import_id),
                )

    def get_import(self, import_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM schedule_file_imports WHERE import_id=?",
                (import_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return dict(row)

    def list_imports(self, project_key: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if project_key:
                cur = conn.execute(
                    "SELECT * FROM schedule_file_imports WHERE project_key=? ORDER BY created_at DESC",
                    (project_key,),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM schedule_file_imports ORDER BY created_at DESC"
                )
            return [dict(r) for r in cur.fetchall()]