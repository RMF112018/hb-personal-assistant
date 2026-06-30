"""Repository for schedule_file_imports rows."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from .connection import open_connection, transaction


class ScheduleImportRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with open_connection(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

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

    def insert_package_assembly_evidence(
        self,
        *,
        lineage_rows: list[dict[str, Any]],
        equivalence_rows: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        def _write(active: sqlite3.Connection) -> None:
            self._insert_rows(
                active,
                "schedule_package_field_lineage",
                lineage_rows,
                replace=True,
            )
            self._insert_rows(
                active,
                "schedule_package_equivalence_facts",
                equivalence_rows,
                replace=True,
            )

        if conn is not None:
            _write(conn)
            return
        with open_connection(self._db_path) as active:
            with transaction(active):
                _write(active)

    def prepare_schedule_package_supersede(
        self,
        *,
        schedule_version_key: str,
        superseded_import_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Mark prior package audit rows superseded and clear active derived rows."""

        def _write(active: sqlite3.Connection) -> None:
            active.execute(
                """
                UPDATE schedule_import_packages
                SET status='superseded'
                WHERE selected_current_schedule_version_key=?
                  AND import_id=?
                  AND status='committed'
                """,
                (schedule_version_key, superseded_import_id),
            )
            baseline_keys = [
                str(row[0])
                for row in active.execute(
                    """
                    SELECT baseline_project_key
                    FROM schedule_baseline_projects
                    WHERE current_schedule_version_key=?
                    """,
                    (schedule_version_key,),
                ).fetchall()
            ]
            if baseline_keys:
                placeholders = ", ".join("?" for _ in baseline_keys)
                for table in (
                    "schedule_baseline_activities",
                    "schedule_baseline_relationships",
                    "schedule_baseline_wbs",
                    "schedule_baseline_activity_codes",
                    "schedule_baseline_udfs",
                ):
                    active.execute(
                        f"DELETE FROM {table} WHERE baseline_project_key IN ({placeholders})",
                        tuple(baseline_keys),
                    )
                active.execute(
                    f"DELETE FROM schedule_baseline_activity_crosswalk WHERE baseline_project_key IN ({placeholders})",
                    tuple(baseline_keys),
                )
                active.execute(
                    f"DELETE FROM schedule_baseline_health_facts WHERE baseline_project_key IN ({placeholders})",
                    tuple(baseline_keys),
                )
            active.execute(
                "DELETE FROM schedule_baseline_projects WHERE current_schedule_version_key=?",
                (schedule_version_key,),
            )
            active.execute(
                "DELETE FROM schedule_source_capabilities WHERE schedule_version_key=?",
                (schedule_version_key,),
            )

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
                  AND status='committed'
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
                      AND (
                        package_id IS NULL
                        OR package_id IN (
                          SELECT package_id FROM schedule_import_packages
                          WHERE selected_current_schedule_version_key=?
                            AND status='committed'
                        )
                      )
                    ORDER BY capability_key
                    """,
                    (schedule_version_key, schedule_version_key),
                ).fetchall()
            ]

    def list_baseline_projects(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT bp.* FROM schedule_baseline_projects bp
                    JOIN schedule_import_packages p ON p.package_id=bp.package_id
                    WHERE bp.current_schedule_version_key=?
                      AND p.status='committed'
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
                    SELECT hf.* FROM schedule_baseline_health_facts hf
                    JOIN schedule_baseline_projects bp
                      ON bp.baseline_project_key=hf.baseline_project_key
                    JOIN schedule_import_packages p ON p.package_id=bp.package_id
                    WHERE hf.current_schedule_version_key=?
                      AND p.status='committed'
                    ORDER BY hf.baseline_project_key, hf.metric_key
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

    def list_package_field_lineage(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT l.* FROM schedule_package_field_lineage l
                    JOIN schedule_import_packages p ON p.package_id=l.package_id
                    WHERE l.schedule_version_key=?
                      AND p.status='committed'
                    ORDER BY l.field_family, l.precedence_rank, l.source_file_id
                    """,
                    (schedule_version_key,),
                ).fetchall()
            ]

    def list_package_equivalence_facts(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT f.* FROM schedule_package_equivalence_facts f
                    JOIN schedule_import_packages p ON p.package_id=f.package_id
                    WHERE f.schedule_version_key=?
                      AND p.status='committed'
                    ORDER BY f.candidate_source_file_id
                    """,
                    (schedule_version_key,),
                ).fetchall()
            ]
