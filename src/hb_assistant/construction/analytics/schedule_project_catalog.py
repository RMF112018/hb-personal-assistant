"""Project catalog for Schedule Intelligence (import picker + browse filters)."""

from __future__ import annotations

import sqlite3
from typing import Any

from hb_assistant.store.connection import get_connection

from .schedule_import_service import ensure_schedule_schema


class ScheduleProjectCatalog:
    """Read project metadata from procore_ep_projects with schedule-import browse fallback."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def _table_exists(self, conn: sqlite3.Connection, table: str) -> bool:
        cur = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        )
        return cur.fetchone() is not None

    def list_selectable_projects(self) -> list[dict[str, Any]]:
        """Projects eligible for new schedule imports (procore_ep_projects only)."""
        ensure_schedule_schema(self._db_path)
        with self._conn() as conn:
            if not self._table_exists(conn, "procore_ep_projects"):
                return []
            cur = conn.execute(
                """
                SELECT project_key,
                       MAX(display_name) AS display_name,
                       MAX(project_number) AS project_number,
                       MAX(project_id) AS procore_project_id,
                       MAX(record_key) AS record_key
                FROM procore_ep_projects
                WHERE project_key IS NOT NULL AND TRIM(project_key) != ''
                GROUP BY project_key
                ORDER BY COALESCE(MAX(display_name), project_key) COLLATE NOCASE
                """
            )
            import_keys = self._committed_import_keys(conn)
            return [
                {
                    "project_key": str(row["project_key"]),
                    "display_name": row["display_name"] or None,
                    "project_number": row["project_number"] or None,
                    "procore_project_id": row["procore_project_id"] or None,
                    "record_key": row["record_key"] or None,
                    "source_system": "procore_ep_projects",
                    "selectable_for_import": True,
                    "has_schedule_imports": str(row["project_key"]) in import_keys,
                }
                for row in cur.fetchall()
            ]

    def list_browse_projects(self) -> list[dict[str, Any]]:
        """Union procore_ep_projects with schedule-only import keys for filters."""
        selectable = {p["project_key"]: p for p in self.list_selectable_projects()}
        ensure_schedule_schema(self._db_path)
        with self._conn() as conn:
            import_keys = self._committed_import_keys(conn)
        out = list(selectable.values())
        for key in sorted(import_keys):
            if key in selectable:
                continue
            out.append(
                {
                    "project_key": key,
                    "display_name": None,
                    "project_number": None,
                    "procore_project_id": None,
                    "record_key": None,
                    "source_system": "schedule_import",
                    "selectable_for_import": False,
                    "has_schedule_imports": True,
                }
            )
        return out

    def catalog_status(self) -> str:
        return "empty" if not self.list_selectable_projects() else "ok"

    def is_selectable_project(self, project_key: str) -> bool:
        key = str(project_key or "").strip()
        if not key:
            return False
        return any(p["project_key"] == key for p in self.list_selectable_projects())

    def resolve_display_name(self, project_key: str) -> str | None:
        key = str(project_key or "").strip()
        if not key:
            return None
        for project in self.list_browse_projects():
            if project["project_key"] == key:
                return project.get("display_name")
        return None

    def get_project(self, project_key: str) -> dict[str, Any] | None:
        key = str(project_key or "").strip()
        if not key:
            return None
        for project in self.list_browse_projects():
            if project["project_key"] == key:
                return project
        return None

    @staticmethod
    def _committed_import_keys(conn: sqlite3.Connection) -> set[str]:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schedule_file_imports'"
        ).fetchone():
            return set()
        cur = conn.execute(
            "SELECT DISTINCT project_key FROM schedule_file_imports WHERE import_status='committed'"
        )
        return {str(r[0]) for r in cur.fetchall() if r[0]}