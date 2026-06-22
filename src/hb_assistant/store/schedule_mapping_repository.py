"""Repository for schedule cost mapping runs, candidates, distributions, weighting."""

from __future__ import annotations

import sqlite3
from typing import Any

from .connection import get_connection


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
        cols = list(row.keys())
        with self._conn() as conn:
            cur = conn.execute(
                f"INSERT INTO schedule_version_diffs ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                tuple(row[c] for c in cols),
            )
            return int(cur.lastrowid or 0)