"""Repository for schedule quality evaluation runs, metrics, and scorecards."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .connection import get_connection, transaction

DEFAULT_PROFILE = "dcma_14_point_plus_gao"
ENGINE_VERSION = "1.0.0"
CHECKER_VERSION = "1.0.0"


class ScheduleQualityRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self._db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def enqueue_evaluation(
        self,
        *,
        evaluation_run_id: str,
        project_key: str,
        schedule_version_key: str,
        schedule_table_id: str | None,
        import_id: str | None,
        assessment_profile: str,
        assessment_profile_version: str,
        method_source: str,
        trigger_source: str,
        idempotency_key: str,
        engine_version: str = ENGINE_VERSION,
        checker_version: str = CHECKER_VERSION,
        queued_at: str,
    ) -> tuple[bool, str]:
        """Insert pending run idempotently. Returns (created, evaluation_run_id)."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                SELECT evaluation_run_id FROM schedule_quality_evaluation_runs
                WHERE schedule_version_key=? AND idempotency_key=?
                """,
                (schedule_version_key, idempotency_key),
            )
            existing = cur.fetchone()
            if existing:
                return False, str(existing[0])
            conn.execute(
                """
                INSERT INTO schedule_quality_evaluation_runs (
                  evaluation_run_id, project_key, schedule_table_id, schedule_version_key,
                  import_id, assessment_profile, assessment_profile_version, method_source,
                  trigger_source, idempotency_key, status, is_latest, queued_at,
                  engine_version, checker_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)
                """,
                (
                    evaluation_run_id,
                    project_key,
                    schedule_table_id,
                    schedule_version_key,
                    import_id,
                    assessment_profile,
                    assessment_profile_version,
                    method_source,
                    trigger_source,
                    idempotency_key,
                    queued_at,
                    engine_version,
                    checker_version,
                ),
            )
        return True, evaluation_run_id

    def claim_pending_run(self, *, started_at: str) -> dict[str, Any] | None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            cur = conn.execute(
                """
                SELECT evaluation_run_id FROM schedule_quality_evaluation_runs
                WHERE status='pending'
                ORDER BY queued_at ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            run_id = str(row[0])
            updated = conn.execute(
                """
                UPDATE schedule_quality_evaluation_runs
                SET status='running', started_at=?
                WHERE evaluation_run_id=? AND status='pending'
                """,
                (started_at, run_id),
            )
            if updated.rowcount != 1:
                return None
            cur2 = conn.execute(
                "SELECT * FROM schedule_quality_evaluation_runs WHERE evaluation_run_id=?",
                (run_id,),
            )
            claimed = cur2.fetchone()
            return dict(claimed) if claimed else None

    def complete_run(
        self,
        *,
        evaluation_run_id: str,
        schedule_version_key: str,
        assessment_profile: str,
        completed_at: str,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                UPDATE schedule_quality_evaluation_runs
                SET is_latest=0
                WHERE schedule_version_key=? AND assessment_profile=? AND is_latest=1
                """,
                (schedule_version_key, assessment_profile),
            )
            conn.execute(
                """
                UPDATE schedule_quality_evaluation_runs
                SET status='completed', completed_at=?, is_latest=1
                WHERE evaluation_run_id=?
                """,
                (completed_at, evaluation_run_id),
            )

    def fail_run(
        self,
        *,
        evaluation_run_id: str,
        error_code: str,
        error_message_redacted: str,
        completed_at: str,
    ) -> None:
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                """
                UPDATE schedule_quality_evaluation_runs
                SET status='failed', completed_at=?, error_code=?, error_message_redacted=?
                WHERE evaluation_run_id=?
                """,
                (completed_at, error_code, error_message_redacted, evaluation_run_id),
            )

    def insert_metric_results(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.executemany(
                f"INSERT INTO schedule_quality_metric_results ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' for _ in cols)})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        return len(rows)

    def insert_scorecard(self, row: dict[str, Any]) -> None:
        cols = list(row.keys())
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.execute(
                f"INSERT INTO schedule_quality_scorecards ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' for _ in cols)})",
                tuple(row[c] for c in cols),
            )

    def insert_findings(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        conn = get_connection(self._db_path)
        with transaction(conn):
            conn.executemany(
                f"INSERT INTO schedule_quality_findings ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' for _ in cols)})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        return len(rows)

    def get_run(self, evaluation_run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM schedule_quality_evaluation_runs WHERE evaluation_run_id=?",
                (evaluation_run_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_pending_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM schedule_quality_evaluation_runs
                WHERE schedule_version_key=? AND status IN ('pending', 'running')
                ORDER BY queued_at DESC LIMIT 1
                """,
                (schedule_version_key,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_latest_run(self, schedule_version_key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM schedule_quality_evaluation_runs
                WHERE schedule_version_key=? AND is_latest=1
                ORDER BY completed_at DESC, queued_at DESC
                LIMIT 1
                """,
                (schedule_version_key,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_scorecard(self, evaluation_run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM schedule_quality_scorecards WHERE evaluation_run_id=?",
                (evaluation_run_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_latest_scorecard(self, schedule_version_key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT s.* FROM schedule_quality_scorecards s
                JOIN schedule_quality_evaluation_runs r ON r.evaluation_run_id = s.evaluation_run_id
                WHERE s.schedule_version_key=? AND r.is_latest=1
                ORDER BY s.created_at DESC
                LIMIT 1
                """,
                (schedule_version_key,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_metrics(self, evaluation_run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM schedule_quality_metric_results
                WHERE evaluation_run_id=?
                ORDER BY metric_family, metric_code
                """,
                (evaluation_run_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_findings(
        self,
        schedule_version_key: str,
        *,
        evaluation_run_id: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if evaluation_run_id:
                cur = conn.execute(
                    """
                    SELECT * FROM schedule_quality_findings
                    WHERE schedule_version_key=? AND evaluation_run_id=?
                    ORDER BY severity, finding_code
                    LIMIT ? OFFSET ?
                    """,
                    (schedule_version_key, evaluation_run_id, limit, offset),
                )
            else:
                latest = self.get_latest_run(schedule_version_key)
                if not latest:
                    cur = conn.execute(
                        """
                        SELECT * FROM schedule_quality_findings
                        WHERE schedule_version_key=? AND evaluation_run_id IS NULL
                        ORDER BY severity, finding_code
                        LIMIT ? OFFSET ?
                        """,
                        (schedule_version_key, limit, offset),
                    )
                else:
                    cur = conn.execute(
                        """
                        SELECT * FROM schedule_quality_findings
                        WHERE schedule_version_key=? AND (
                          evaluation_run_id=? OR evaluation_run_id IS NULL
                        )
                        ORDER BY severity, finding_code
                        LIMIT ? OFFSET ?
                        """,
                        (schedule_version_key, latest["evaluation_run_id"], limit, offset),
                    )
            return [dict(r) for r in cur.fetchall()]

    def list_project_quality_summary(self, project_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT DISTINCT schedule_version_key FROM schedule_file_imports
                WHERE project_key=? AND import_status='committed'
                ORDER BY created_at DESC
                """,
                (project_key,),
            )
            versions = [str(r[0]) for r in cur.fetchall()]
        out: list[dict[str, Any]] = []
        for svk in versions:
            run = self.get_latest_run(svk)
            scorecard = self.get_latest_scorecard(svk) if run else None
            out.append(
                {
                    "schedule_version_key": svk,
                    "quality_status": run.get("status") if run else "not_evaluated",
                    "quality_score": scorecard.get("quality_score") if scorecard else None,
                    "quality_grade": scorecard.get("quality_grade") if scorecard else None,
                    "assessment_profile": run.get("assessment_profile") if run else None,
                    "evaluation_run_id": run.get("evaluation_run_id") if run else None,
                }
            )
        return out

    @staticmethod
    def parse_json_field(value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except json.JSONDecodeError:
            return default