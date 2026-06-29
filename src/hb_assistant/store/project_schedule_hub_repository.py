"""Repository for Project Schedule Hub Phase 2 persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .connection import get_connection, open_connection, transaction

MEMBERSHIP_ACCEPTED = "accepted"
MEMBERSHIP_EXCLUDED = "excluded"
MEMBERSHIP_PENDING = "pending_review"

REVIEW_OPEN = "open"
REVIEW_REVIEWED = "reviewed"
REVIEW_DISMISSED = "dismissed"
REVIEW_WATCHING = "watching"
REVIEW_STATUSES = frozenset({REVIEW_OPEN, REVIEW_REVIEWED, REVIEW_DISMISSED, REVIEW_WATCHING})


class ProjectScheduleHubRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self._db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def get_membership(
        self, *, project_key: str, schedule_version_key: str
    ) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM project_schedule_series_membership
                WHERE project_key=? AND schedule_version_key=?
                """,
                (project_key, schedule_version_key),
            ).fetchone()
            return dict(row) if row else None

    def list_memberships(self, *, project_key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM project_schedule_series_membership
                WHERE project_key=?
                ORDER BY updated_at DESC, schedule_version_key
                """,
                (project_key,),
            ).fetchall()
            return [dict(row) for row in rows]

    def upsert_membership(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        import_id: str | None,
        membership_status: str,
        review_reason: str | None = None,
        reviewed_by_operator: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_membership(
            project_key=project_key, schedule_version_key=schedule_version_key
        )
        evidence_json = json.dumps(evidence or {}, sort_keys=True, default=str)
        reviewed_at = now if reviewed_by_operator else (existing or {}).get("reviewed_at")
        with open_connection(self._db_path) as conn:
            if existing:
                conn.execute(
                    """
                    UPDATE project_schedule_series_membership
                    SET import_id=?,
                        membership_status=?,
                        review_reason=?,
                        reviewed_by_operator=COALESCE(?, reviewed_by_operator),
                        reviewed_at=COALESCE(?, reviewed_at),
                        evidence_json=?,
                        updated_at=?
                    WHERE membership_id=?
                    """,
                    (
                        import_id,
                        membership_status,
                        review_reason,
                        reviewed_by_operator,
                        reviewed_at,
                        evidence_json,
                        now,
                        existing["membership_id"],
                    ),
                )
                membership_id = str(existing["membership_id"])
            else:
                membership_id = f"psm-{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO project_schedule_series_membership (
                      membership_id, project_key, schedule_version_key, import_id,
                      membership_status, review_reason, reviewed_by_operator, reviewed_at,
                      evidence_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        membership_id,
                        project_key,
                        schedule_version_key,
                        import_id,
                        membership_status,
                        review_reason,
                        reviewed_by_operator,
                        reviewed_at,
                        evidence_json,
                        now,
                        now,
                    ),
                )
            conn.commit()
        return self.get_membership(project_key=project_key, schedule_version_key=schedule_version_key) or {}

    def get_active_baseline_selection(
        self, *, project_key: str, current_schedule_version_key: str
    ) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM project_schedule_baseline_selections
                WHERE project_key=?
                  AND current_schedule_version_key=?
                  AND selection_status='active'
                ORDER BY selected_at DESC, updated_at DESC
                LIMIT 1
                """,
                (project_key, current_schedule_version_key),
            ).fetchone()
            return dict(row) if row else None

    def set_baseline_selection(
        self,
        *,
        project_key: str,
        current_schedule_version_key: str,
        selected_baseline_schedule_version_key: str,
        selected_by_operator: str | None,
        selection_note: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                conn.execute(
                    """
                    UPDATE project_schedule_baseline_selections
                    SET selection_status='superseded', updated_at=?
                    WHERE project_key=?
                      AND current_schedule_version_key=?
                      AND selection_status='active'
                    """,
                    (now, project_key, current_schedule_version_key),
                )
                selection_id = f"pbs-{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO project_schedule_baseline_selections (
                      selection_id, project_key, current_schedule_version_key,
                      selected_baseline_schedule_version_key, selection_status,
                      selected_by_operator, selected_at, selection_note,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
                    """,
                    (
                        selection_id,
                        project_key,
                        current_schedule_version_key,
                        selected_baseline_schedule_version_key,
                        selected_by_operator,
                        now,
                        selection_note,
                        now,
                        now,
                    ),
                )
        return self.get_active_baseline_selection(
            project_key=project_key,
            current_schedule_version_key=current_schedule_version_key,
        ) or {}

    def list_review_items(
        self,
        *,
        project_key: str,
        schedule_version_key: str | None = None,
        review_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["project_key=?"]
        params: list[Any] = [project_key]
        if schedule_version_key:
            clauses.append("schedule_version_key=?")
            params.append(schedule_version_key)
        if review_status:
            clauses.append("review_status=?")
            params.append(review_status)
        params.extend((limit, offset))
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM project_schedule_review_items
                WHERE {' AND '.join(clauses)}
                ORDER BY priority DESC, item_title, stable_item_key
                LIMIT ? OFFSET ?
                """,
                tuple(params),
            ).fetchall()
            return [self._review_item_row(dict(row)) for row in rows]

    def get_review_item(self, *, review_item_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM project_schedule_review_items WHERE review_item_id=?",
                (review_item_id,),
            ).fetchone()
            return self._review_item_row(dict(row)) if row else None

    def get_latest_review_item_by_stable_key(
        self, *, project_key: str, stable_item_key: str
    ) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM project_schedule_review_items
                WHERE project_key=? AND stable_item_key=?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (project_key, stable_item_key),
            ).fetchone()
            return self._review_item_row(dict(row)) if row else None

    def upsert_review_item(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        stable_item_key: str,
        item_type: str,
        item_title: str,
        priority: int,
        evidence: dict[str, Any] | None = None,
        source_activity_id: str | None = None,
        inherit_status_from_project: bool = True,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            existing = conn.execute(
                """
                SELECT * FROM project_schedule_review_items
                WHERE project_key=? AND schedule_version_key=? AND stable_item_key=?
                """,
                (project_key, schedule_version_key, stable_item_key),
            ).fetchone()
            evidence_json = json.dumps(evidence or {}, sort_keys=True, default=str)
            if existing:
                conn.execute(
                    """
                    UPDATE project_schedule_review_items
                    SET item_type=?, item_title=?, priority=?, evidence_json=?,
                        source_activity_id=?, updated_at=?
                    WHERE review_item_id=?
                    """,
                    (
                        item_type,
                        item_title,
                        priority,
                        evidence_json,
                        source_activity_id,
                        now,
                        existing["review_item_id"],
                    ),
                )
                review_item_id = str(existing["review_item_id"])
            else:
                review_status = REVIEW_OPEN
                pm_notes = None
                reviewed_by_operator = None
                reviewed_at = None
                if inherit_status_from_project:
                    prior = conn.execute(
                        """
                        SELECT review_status, pm_notes, reviewed_by_operator, reviewed_at
                        FROM project_schedule_review_items
                        WHERE project_key=? AND stable_item_key=?
                        ORDER BY updated_at DESC
                        LIMIT 1
                        """,
                        (project_key, stable_item_key),
                    ).fetchone()
                    if prior:
                        review_status = str(prior["review_status"])
                        pm_notes = prior["pm_notes"]
                        reviewed_by_operator = prior["reviewed_by_operator"]
                        reviewed_at = prior["reviewed_at"]
                review_item_id = f"psri-{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO project_schedule_review_items (
                      review_item_id, project_key, schedule_version_key, stable_item_key,
                      item_type, item_title, priority, review_status, pm_notes, evidence_json,
                      source_activity_id, reviewed_by_operator, reviewed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        review_item_id,
                        project_key,
                        schedule_version_key,
                        stable_item_key,
                        item_type,
                        item_title,
                        priority,
                        review_status,
                        pm_notes,
                        evidence_json,
                        source_activity_id,
                        reviewed_by_operator,
                        reviewed_at,
                        now,
                        now,
                    ),
                )
            conn.commit()
        return self.get_review_item(review_item_id=review_item_id) or {}

    def update_review_item(
        self,
        *,
        review_item_id: str,
        review_status: str | None = None,
        pm_notes: str | None = None,
        reviewed_by_operator: str | None = None,
    ) -> dict[str, Any] | None:
        if review_status is not None and review_status not in REVIEW_STATUSES:
            raise ValueError("invalid_review_status")
        now = datetime.now(timezone.utc).isoformat()
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT review_item_id FROM project_schedule_review_items WHERE review_item_id=?",
                (review_item_id,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                """
                UPDATE project_schedule_review_items
                SET review_status=COALESCE(?, review_status),
                    pm_notes=COALESCE(?, pm_notes),
                    reviewed_by_operator=COALESCE(?, reviewed_by_operator),
                    reviewed_at=CASE WHEN ? IS NOT NULL THEN ? ELSE reviewed_at END,
                    updated_at=?
                WHERE review_item_id=?
                """,
                (
                    review_status,
                    pm_notes,
                    reviewed_by_operator,
                    reviewed_by_operator,
                    now,
                    now,
                    review_item_id,
                ),
            )
            conn.commit()
        return self.get_review_item(review_item_id=review_item_id)

    @staticmethod
    def _review_item_row(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        if out.get("evidence_json"):
            try:
                out["evidence"] = json.loads(str(out["evidence_json"]))
            except json.JSONDecodeError:
                out["evidence"] = {}
        else:
            out["evidence"] = {}
        return out