"""Read-only project summary list for the Projects entry page."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

_SURFACE = "analytics.projects.list"
_TABLE = "procore_ep_projects"


class ProjectSummaryReadModelError(RuntimeError):
    """Raised when project summaries cannot be read safely."""


def _guardrails() -> dict[str, Any]:
    return {
        "read_only": True,
        "no_db_write": True,
        "local_first": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
    }


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pick_canonical_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    current_rows = [row for row in rows if _int_value(row.get("is_current")) == 1]
    pool = current_rows or rows
    return max(
        pool,
        key=lambda row: (
            str(row.get("updated_utc") or ""),
            str(row.get("record_key") or ""),
        ),
    )


def _column_expr(columns: set[str], column: str, alias: str | None = None) -> str:
    out = alias or column
    if column in columns:
        return f'"{column}" AS "{out}"'
    return f'NULL AS "{out}"'


class ProjectSummaryReadModelService:
    """Read safe project summaries from ``procore_ep_projects`` without writes."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    def build(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            if not self._table_exists(conn):
                return self._empty()
            columns = self._columns(conn)
            if "project_key" not in columns:
                return self._empty()
            rows = self._load_rows(conn, columns)
        finally:
            conn.close()
        return {
            "surface": _SURFACE,
            "projects": self._summaries(rows),
            "guardrails": _guardrails(),
        }

    def _empty(self) -> dict[str, Any]:
        return {
            "surface": _SURFACE,
            "projects": [],
            "guardrails": _guardrails(),
        }

    def _resolved_db_path(self) -> Path:
        return Path(self.db_path) if self.db_path is not None else PathPolicy().get_db_path()

    def _connect(self) -> sqlite3.Connection:
        path = self._resolved_db_path()
        if not path.exists():
            raise ProjectSummaryReadModelError("project summary DB is not available")
        try:
            conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ProjectSummaryReadModelError(
                "project summary DB could not be opened read-only"
            ) from exc
        return conn

    def _table_exists(self, conn: sqlite3.Connection) -> bool:
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (_TABLE,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise ProjectSummaryReadModelError("project summary schema is unreadable") from exc
        return row is not None

    def _columns(self, conn: sqlite3.Connection) -> set[str]:
        try:
            return {str(row["name"]) for row in conn.execute(f'PRAGMA table_info("{_TABLE}")')}
        except sqlite3.Error as exc:
            raise ProjectSummaryReadModelError("project summary columns are unreadable") from exc

    def _load_rows(self, conn: sqlite3.Connection, columns: set[str]) -> list[dict[str, Any]]:
        status_expr = (
            _column_expr(columns, "status")
            if "status" in columns
            else _column_expr(columns, "stage", "status")
        )
        select_columns = [
            _column_expr(columns, "project_key"),
            _column_expr(columns, "project_id", "procore_project_id"),
            _column_expr(columns, "display_name"),
            _column_expr(columns, "address"),
            _column_expr(columns, "city"),
            _column_expr(columns, "state_code"),
            _column_expr(columns, "zip"),
            _column_expr(columns, "project_number"),
            status_expr,
            _column_expr(columns, "record_key"),
            _column_expr(columns, "is_current"),
            _column_expr(columns, "updated_utc"),
        ]
        sql = (
            f"SELECT {', '.join(select_columns)} FROM {_TABLE} "
            "WHERE project_key IS NOT NULL AND TRIM(project_key) != ''"
        )
        try:
            return [dict(row) for row in conn.execute(sql).fetchall()]
        except sqlite3.Error as exc:
            raise ProjectSummaryReadModelError("project summary rows are unreadable") from exc

    def _summaries(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            project_key = _clean_string(row.get("project_key"))
            if project_key:
                grouped[project_key].append(row)

        projects: list[dict[str, Any]] = []
        for project_key, key_rows in grouped.items():
            row = _pick_canonical_row(key_rows)
            projects.append(
                {
                    "project_key": project_key,
                    "procore_project_id": _clean_string(row.get("procore_project_id")),
                    "display_name": _clean_string(row.get("display_name")),
                    "address": _clean_string(row.get("address")),
                    "city": _clean_string(row.get("city")),
                    "state_code": _clean_string(row.get("state_code")),
                    "zip": _clean_string(row.get("zip")),
                    "project_number": _clean_string(row.get("project_number")),
                    "status": _clean_string(row.get("status")),
                }
            )

        projects.sort(
            key=lambda project: (
                str(project.get("display_name") or project["project_key"]).casefold(),
                str(project["project_key"]).casefold(),
            )
        )
        return projects
