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

    @staticmethod
    def _insert_rows(
        conn: sqlite3.Connection,
        table: str,
        rows: list[dict[str, Any]],
        *,
        replace: bool = False,
    ) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        verb = "INSERT OR REPLACE" if replace else "INSERT"
        sql = (
            f"{verb} INTO {table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})"
        )
        conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
        return len(rows)

    def insert_schedule_package(
        self,
        package: dict[str, Any],
        *,
        files: list[dict[str, Any]] | None = None,
        capabilities: list[dict[str, Any]] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        def _write(active: sqlite3.Connection) -> None:
            self._insert_rows(active, "schedule_import_packages", [package], replace=True)
            self._insert_rows(active, "schedule_import_package_files", files or [], replace=True)
            self._insert_rows(active, "schedule_source_capabilities", capabilities or [], replace=True)

        if conn is not None:
            _write(conn)
            return
        with open_connection(self._db_path) as active:
            with transaction(active):
                _write(active)

    def insert_baseline_evidence(
        self,
        *,
        baseline_projects: list[dict[str, Any]],
        baseline_activities: list[dict[str, Any]],
        baseline_relationships: list[dict[str, Any]],
        baseline_wbs: list[dict[str, Any]],
        baseline_codes: list[dict[str, Any]],
        baseline_udfs: list[dict[str, Any]],
        crosswalks: list[dict[str, Any]],
        health_facts: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        def _write(active: sqlite3.Connection) -> None:
            self._insert_rows(active, "schedule_baseline_projects", baseline_projects, replace=True)
            self._insert_rows(active, "schedule_baseline_activities", baseline_activities)
            self._insert_rows(active, "schedule_baseline_relationships", baseline_relationships)
            self._insert_rows(active, "schedule_baseline_wbs", baseline_wbs)
            self._insert_rows(active, "schedule_baseline_activity_codes", baseline_codes)
            self._insert_rows(active, "schedule_baseline_udfs", baseline_udfs)
            self._insert_rows(active, "schedule_baseline_activity_crosswalk", crosswalks, replace=True)
            self._insert_rows(active, "schedule_baseline_health_facts", health_facts, replace=True)

        if conn is not None:
            _write(conn)
            return
        with open_connection(self._db_path) as active:
            with transaction(active):
                _write(active)

    def insert_diff_facts(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        if conn is not None:
            return self._insert_rows(conn, "schedule_version_diff_facts", rows, replace=True)
        with open_connection(self._db_path) as active:
            with transaction(active):
                return self._insert_rows(active, "schedule_version_diff_facts", rows, replace=True)

    def insert_capabilities(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        if conn is not None:
            return self._insert_rows(conn, "schedule_source_capabilities", rows, replace=True)
        with open_connection(self._db_path) as active:
            with transaction(active):
                return self._insert_rows(active, "schedule_source_capabilities", rows, replace=True)

    def get_package_for_version(self, schedule_version_key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM schedule_import_packages
                WHERE selected_current_schedule_version_key=?
                ORDER BY committed_at DESC, created_at DESC LIMIT 1
                """,
                (schedule_version_key,),
            ).fetchone()
            return dict(row) if row else None

    def list_capabilities(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT * FROM schedule_source_capabilities
                    WHERE schedule_version_key=?
                    ORDER BY capability_key
                    """,
                    (schedule_version_key,),
                ).fetchall()
            ]

    def list_baseline_projects(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT * FROM schedule_baseline_projects
                    WHERE current_schedule_version_key=?
                    ORDER BY baseline_project_name, baseline_project_id
                    """,
                    (schedule_version_key,),
                ).fetchall()
            ]

    def list_baseline_health_facts(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT * FROM schedule_baseline_health_facts
                    WHERE current_schedule_version_key=?
                    ORDER BY baseline_project_key, metric_key
                    """,
                    (schedule_version_key,),
                ).fetchall()
            ]

    def list_diff_facts(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT * FROM schedule_version_diff_facts
                    WHERE to_schedule_version_key=?
                    ORDER BY diff_id DESC, metric_key
                    """,
                    (schedule_version_key,),
                ).fetchall()
            ]
