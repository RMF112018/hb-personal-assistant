"""Repository for schedule cost mapping runs, candidates, distributions, weighting."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable

from .connection import get_connection, open_connection, transaction


class ScheduleMappingRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self._db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def insert_mapping_run(self, row: dict[str, Any]) -> None:
        cols = list(row.keys())
        with self._conn() as conn:
            conn.execute(
                f"INSERT INTO schedule_cost_mapping_runs ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                tuple(row[c] for c in cols),
            )

    def get_mapping_run(self, mapping_run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM schedule_cost_mapping_runs WHERE mapping_run_id=?",
                (mapping_run_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def approve_mapping_run(self, mapping_run_id: str, *, approved_at: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE schedule_cost_mapping_runs
                SET mapping_status='approved', approved_at=?
                WHERE mapping_run_id=?
                """,
                (approved_at, mapping_run_id),
            )

    def insert_candidates(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        with self._conn() as conn:
            conn.executemany(
                f"INSERT INTO schedule_cost_mapping_candidates ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        return len(rows)

    def list_candidates(self, mapping_run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM schedule_cost_mapping_candidates WHERE mapping_run_id=? ORDER BY activity_id",
                (mapping_run_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def review_candidate(
        self,
        candidate_id: int,
        *,
        operator_status: str,
        operator_notes_redacted: str | None,
        reviewed_at: str,
        reviewed_by_operator: str | None,
        candidate_cost_code: str | None = None,
    ) -> None:
        with self._conn() as conn:
            if candidate_cost_code is not None:
                conn.execute(
                    """
                    UPDATE schedule_cost_mapping_candidates
                    SET operator_status=?, operator_notes_redacted=?,
                        reviewed_at=?, reviewed_by_operator=?,
                        candidate_cost_code=?
                    WHERE id=?
                    """,
                    (
                        operator_status,
                        operator_notes_redacted,
                        reviewed_at,
                        reviewed_by_operator,
                        candidate_cost_code,
                        candidate_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE schedule_cost_mapping_candidates
                    SET operator_status=?, operator_notes_redacted=?,
                        reviewed_at=?, reviewed_by_operator=?
                    WHERE id=?
                    """,
                    (
                        operator_status,
                        operator_notes_redacted,
                        reviewed_at,
                        reviewed_by_operator,
                        candidate_id,
                    ),
                )

    def insert_distributions(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        with self._conn() as conn:
            conn.executemany(
                f"INSERT INTO schedule_cost_distributions ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        return len(rows)

    def list_distributions(self, mapping_run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM schedule_cost_distributions WHERE mapping_run_id=?",
                (mapping_run_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def insert_weighting_results(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        with self._conn() as conn:
            conn.executemany(
                f"INSERT INTO schedule_cost_weighting_results ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        return len(rows)

    def list_weighting_results(
        self, project_key: str, *, approved_only: bool = True
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if approved_only:
                cur = conn.execute(
                    """
                    SELECT w.* FROM schedule_cost_weighting_results w
                    JOIN schedule_cost_mapping_runs r ON r.mapping_run_id = w.mapping_run_id
                    WHERE w.project_key=? AND r.mapping_status='approved'
                    ORDER BY w.created_at DESC
                    """,
                    (project_key,),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM schedule_cost_weighting_results WHERE project_key=?",
                    (project_key,),
                )
            return [dict(r) for r in cur.fetchall()]

    def insert_quality_findings(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        with self._conn() as conn:
            conn.executemany(
                f"INSERT INTO schedule_quality_findings ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        return len(rows)

    def list_quality_findings(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM schedule_quality_findings WHERE schedule_version_key=? ORDER BY severity, finding_code",
                (schedule_version_key,),
            )
            return [dict(r) for r in cur.fetchall()]

    def insert_version_diff(self, row: dict[str, Any]) -> int:
        with self._conn() as conn:
            table_cols = {
                r[1] for r in conn.execute("PRAGMA table_info(schedule_version_diffs)").fetchall()
            }
            cols = [c for c in row.keys() if c in table_cols]
            cur = conn.execute(
                f"INSERT INTO schedule_version_diffs ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                tuple(row[c] for c in cols),
            )
            return int(cur.lastrowid or 0)

    def insert_version_diff_with_details(
        self,
        row: dict[str, Any],
        *,
        detail_rows: list[dict[str, Any]] | None = None,
        diff_fact_rows: list[dict[str, Any]] | None = None,
    ) -> int:
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                table_cols = {
                    r[1]
                    for r in conn.execute("PRAGMA table_info(schedule_version_diffs)").fetchall()
                }
                cols = [c for c in row.keys() if c in table_cols]
                cur = conn.execute(
                    f"INSERT INTO schedule_version_diffs ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                    tuple(row[c] for c in cols),
                )
                diff_id = int(cur.lastrowid or 0)
                if detail_rows:
                    self.replace_diff_detail_facts(conn, diff_id=diff_id, rows=detail_rows)
                if diff_fact_rows:
                    self._insert_rows(conn, "schedule_version_diff_facts", diff_fact_rows, replace=True)
                return diff_id

    def insert_version_diff_with_detail_builders(
        self,
        row: dict[str, Any],
        *,
        detail_builder: Callable[[int], list[dict[str, Any]]] | None = None,
        diff_fact_builder: Callable[[int], list[dict[str, Any]]] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                table_cols = {
                    r[1]
                    for r in conn.execute("PRAGMA table_info(schedule_version_diffs)").fetchall()
                }
                cols = [c for c in row.keys() if c in table_cols]
                cur = conn.execute(
                    f"INSERT INTO schedule_version_diffs ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                    tuple(row[c] for c in cols),
                )
                diff_id = int(cur.lastrowid or 0)
                details = detail_builder(diff_id) if detail_builder else []
                self.replace_diff_detail_facts(conn, diff_id=diff_id, rows=details)
                facts = diff_fact_builder(diff_id) if diff_fact_builder else []
                if facts:
                    self._insert_rows(conn, "schedule_version_diff_facts", facts, replace=True)
                return diff_id, details

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
        conn.executemany(
            f"{verb} INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            [tuple(row.get(c) for c in cols) for row in rows],
        )
        return len(rows)

    def replace_diff_detail_facts(
        self, conn: sqlite3.Connection, *, diff_id: int, rows: list[dict[str, Any]]
    ) -> int:
        conn.execute("DELETE FROM schedule_version_diff_detail_facts WHERE diff_id=?", (diff_id,))
        if not rows:
            return 0
        return self._insert_rows(conn, "schedule_version_diff_detail_facts", rows, replace=True)

    def get_version_diff(self, diff_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM schedule_version_diffs WHERE id=?",
                (diff_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_diff_detail_facts(
        self,
        diff_id: int,
        *,
        project_key: str | None = None,
        change_domain: str | None = None,
        change_type: str | None = None,
        severity: str | None = None,
        requires_attention: bool | None = None,
        wbs_code: str | None = None,
        activity_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["diff_id=?"]
        params: list[Any] = [diff_id]
        if project_key:
            clauses.append("project_key=?")
            params.append(project_key)
        if change_domain:
            clauses.append("change_domain=?")
            params.append(change_domain)
        if change_type:
            clauses.append("change_type=?")
            params.append(change_type)
        if severity:
            clauses.append("severity=?")
            params.append(severity)
        if requires_attention is not None:
            clauses.append("requires_attention=?")
            params.append(1 if requires_attention else 0)
        if wbs_code:
            clauses.append("wbs_code=?")
            params.append(wbs_code)
        if activity_id:
            clauses.append("(activity_id LIKE ? OR activity_name LIKE ?)")
            params.extend((f"%{activity_id}%", f"%{activity_id}%"))
        params.extend((limit, offset))
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM schedule_version_diff_detail_facts
                WHERE {' AND '.join(clauses)}
                ORDER BY
                  CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'major' THEN 2
                    WHEN 'moderate' THEN 3
                    WHEN 'minor' THEN 4
                    ELSE 5
                  END,
                  change_domain,
                  activity_id,
                  detail_id
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_diff_detail_facts(self, diff_id: int, *, project_key: str | None = None) -> int:
        clauses = ["diff_id=?"]
        params: list[Any] = [diff_id]
        if project_key:
            clauses.append("project_key=?")
            params.append(project_key)
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM schedule_version_diff_detail_facts WHERE {' AND '.join(clauses)}",
                tuple(params),
            ).fetchone()
            return int(row[0] if row else 0)

    def summarize_diff_detail_facts(
        self, diff_id: int, *, project_key: str | None = None
    ) -> dict[str, Any]:
        rows = self.list_diff_detail_facts(
            diff_id, project_key=project_key, limit=100000, offset=0
        )
        from hb_assistant.construction.analytics.schedule_diff_intelligence import (
            summarize_detail_facts,
        )

        return summarize_detail_facts(rows)
