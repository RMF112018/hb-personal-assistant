"""Project catalog for Schedule Intelligence (import picker + browse filters)."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Iterator

from hb_assistant.store.connection import open_connection

from .schedule_import_service import ensure_schedule_schema

WARNING_INCONSISTENT_WITHIN_KEY = "inconsistent_display_metadata_within_project_key"
WARNING_MULTIPLE_CURRENT = "multiple_current_rows"
WARNING_DUPLICATE_ACROSS_KEYS = "duplicate_display_metadata_across_project_keys"


def format_project_identity_label(
    *,
    project_key: str,
    display_name: str | None,
    project_number: str | None,
    procore_project_id: str | None,
    identity_warning: str | None = None,
) -> str:
    """Build a key-first label safe for import picker options."""
    name = (display_name or "").strip() or "display unavailable"
    parts = [f"{project_key} — {name}"]
    if project_number:
        parts.append(f"#{project_number}")
    if procore_project_id:
        parts.append(f"Procore {procore_project_id}")
    label = " · ".join(parts)
    if identity_warning:
        label = f"{label} ⚠"
    return label


def _distinct_non_empty(values: list[str | None]) -> set[str]:
    return {str(v).strip() for v in values if v is not None and str(v).strip()}


def _pick_canonical_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    current_rows = [row for row in rows if int(row.get("is_current") or 0) == 1]
    pool = current_rows or rows
    return max(
        pool,
        key=lambda row: (
            str(row.get("updated_utc") or ""),
            str(row.get("record_key") or ""),
        ),
    )


def _within_key_warnings(rows: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    display_names = _distinct_non_empty([row.get("display_name") for row in rows])
    project_numbers = _distinct_non_empty([row.get("project_number") for row in rows])
    project_ids = _distinct_non_empty([row.get("project_id") for row in rows])
    if len(display_names) > 1 or len(project_numbers) > 1 or len(project_ids) > 1:
        warnings.append(WARNING_INCONSISTENT_WITHIN_KEY)
    current_count = sum(1 for row in rows if int(row.get("is_current") or 0) == 1)
    if current_count > 1:
        warnings.append(WARNING_MULTIPLE_CURRENT)
    return warnings


def _join_warnings(*groups: list[str]) -> str | None:
    codes: list[str] = []
    for group in groups:
        for code in group:
            if code not in codes:
                codes.append(code)
    return ", ".join(codes) if codes else None


class ScheduleProjectCatalog:
    """Read project metadata from procore_ep_projects with schedule-import browse fallback."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with open_connection(self._db_path) as conn:
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def _table_exists(self, conn: sqlite3.Connection, table: str) -> bool:
        cur = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        )
        return cur.fetchone() is not None

    def _load_ep_project_rows(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        cur = conn.execute(
            """
            SELECT project_key,
                   record_key,
                   display_name,
                   project_number,
                   project_id,
                   is_current,
                   updated_utc
            FROM procore_ep_projects
            WHERE project_key IS NOT NULL AND TRIM(project_key) != ''
            """
        )
        return [dict(row) for row in cur.fetchall()]

    def _resolve_selectable_projects(
        self, conn: sqlite3.Connection, import_keys: set[str]
    ) -> list[dict[str, Any]]:
        rows = self._load_ep_project_rows(conn)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["project_key"])].append(row)

        resolved: list[dict[str, Any]] = []
        for project_key in sorted(grouped):
            group_rows = grouped[project_key]
            canonical = _pick_canonical_row(group_rows)
            within_warnings = _within_key_warnings(group_rows)
            display_name = canonical.get("display_name") or None
            project_number = canonical.get("project_number") or None
            procore_project_id = canonical.get("project_id") or None
            identity_warning = _join_warnings(within_warnings)
            project_identity_label = format_project_identity_label(
                project_key=project_key,
                display_name=display_name,
                project_number=project_number,
                procore_project_id=procore_project_id,
                identity_warning=identity_warning,
            )
            resolved.append(
                {
                    "project_key": project_key,
                    "display_name": display_name,
                    "project_number": project_number,
                    "procore_project_id": procore_project_id,
                    "record_key": canonical.get("record_key") or None,
                    "source_system": "procore_ep_projects",
                    "display_label": project_identity_label,
                    "project_identity_label": project_identity_label,
                    "identity_warning": identity_warning,
                    "selectable_for_import": True,
                    "has_schedule_imports": project_key in import_keys,
                }
            )

        display_index: dict[tuple[str, str], list[str]] = defaultdict(list)
        for project in resolved:
            display_name = str(project.get("display_name") or "").strip()
            project_number = str(project.get("project_number") or "").strip()
            if display_name and project_number:
                display_index[(display_name, project_number)].append(project["project_key"])

        duplicate_keys = {
            key
            for keys in display_index.values()
            if len(keys) > 1
            for key in keys
        }
        if duplicate_keys:
            for project in resolved:
                if project["project_key"] not in duplicate_keys:
                    continue
                project["identity_warning"] = _join_warnings(
                    [w for w in (project.get("identity_warning") or "").split(", ") if w],
                    [WARNING_DUPLICATE_ACROSS_KEYS],
                )
                project["project_identity_label"] = format_project_identity_label(
                    project_key=project["project_key"],
                    display_name=project.get("display_name"),
                    project_number=project.get("project_number"),
                    procore_project_id=project.get("procore_project_id"),
                    identity_warning=project.get("identity_warning"),
                )
                project["display_label"] = project["project_identity_label"]

        resolved.sort(
            key=lambda project: (
                str(project.get("display_name") or project["project_key"]).casefold(),
                project["project_key"].casefold(),
            )
        )
        return resolved

    def list_selectable_projects(self) -> list[dict[str, Any]]:
        """Projects eligible for new schedule imports (procore_ep_projects only)."""
        ensure_schedule_schema(self._db_path)
        with self._conn() as conn:
            if not self._table_exists(conn, "procore_ep_projects"):
                return []
            import_keys = self._committed_import_keys(conn)
            return self._resolve_selectable_projects(conn, import_keys)

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
            label = format_project_identity_label(
                project_key=key,
                display_name=None,
                project_number=None,
                procore_project_id=None,
            )
            out.append(
                {
                    "project_key": key,
                    "display_name": None,
                    "project_number": None,
                    "procore_project_id": None,
                    "record_key": None,
                    "source_system": "schedule_import",
                    "display_label": label,
                    "project_identity_label": label,
                    "identity_warning": None,
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