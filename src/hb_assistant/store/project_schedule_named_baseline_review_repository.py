"""Scoped persistence for named-baseline review workbench items."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from .connection import open_connection
from .project_schedule_hub_repository import (
    EVENT_CREATED,
    EVENT_NOTES_CHANGED,
    EVENT_STATUS_CHANGED,
    EVENT_SYNCED,
    REVIEW_OPEN,
    REVIEW_STATUSES,
)

NAMED_REVIEW_ITEM_ID_PREFIX = "psnbri-"


@dataclass(frozen=True)
class NamedBaselineReviewScope:
    project_key: str
    current_schedule_version_key: str
    comparison_basis: str
    baseline_slot_key: str
    baseline_slot_label: str | None
    baseline_selection_id: str | None
    baseline_schedule_version_key: str
    baseline_schedule_data_date: str | None
    baseline_display_name: str | None
    schedule_data_date: str | None
    as_of_date: str | None


@dataclass(frozen=True)
class NamedBaselineReviewIdentity:
    project_key: str
    current_schedule_version_key: str
    comparison_basis: str
    baseline_schedule_version_key: str
    source_stable_key: str
    source_metric_key: str
    source_signal_type: str
    source_activity_id: str | None


class ProjectScheduleNamedBaselineReviewRepository:
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

    @staticmethod
    def is_named_review_item_id(review_item_id: str) -> bool:
        return str(review_item_id).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)

    def get_review_item(self, *, review_item_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM project_schedule_named_baseline_review_items WHERE review_item_id=?",
                (review_item_id,),
            ).fetchone()
            return self._row(dict(row)) if row else None

    def get_by_identity(
        self,
        *,
        identity: NamedBaselineReviewIdentity,
    ) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM project_schedule_named_baseline_review_items
                WHERE project_key=?
                  AND current_schedule_version_key=?
                  AND comparison_basis=?
                  AND baseline_schedule_version_key=?
                  AND source_stable_key=?
                  AND source_metric_key=?
                  AND source_signal_type=?
                  AND COALESCE(source_activity_id, '') = COALESCE(?, '')
                """,
                (
                    identity.project_key,
                    identity.current_schedule_version_key,
                    identity.comparison_basis,
                    identity.baseline_schedule_version_key,
                    identity.source_stable_key,
                    identity.source_metric_key,
                    identity.source_signal_type,
                    identity.source_activity_id,
                ),
            ).fetchone()
            return self._row(dict(row)) if row else None

    def list_in_scope(
        self,
        *,
        scope: NamedBaselineReviewScope,
        review_status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses = [
            "project_key=?",
            "current_schedule_version_key=?",
            "comparison_basis=?",
            "baseline_schedule_version_key=?",
        ]
        params: list[Any] = [
            scope.project_key,
            scope.current_schedule_version_key,
            scope.comparison_basis,
            scope.baseline_schedule_version_key,
        ]
        if review_status:
            clauses.append("review_status=?")
            params.append(review_status)
        params.append(max(1, min(limit, 500)))
        sql = f"""
            SELECT * FROM project_schedule_named_baseline_review_items
            WHERE {' AND '.join(clauses)}
            ORDER BY priority DESC, item_title ASC
            LIMIT ?
        """
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row(dict(row)) for row in rows]

    def upsert_from_candidate(
        self,
        *,
        scope: NamedBaselineReviewScope,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        evidence = dict(candidate.get("evidence") or {})
        identity = self._identity_from_candidate(scope, candidate)
        now = datetime.now(timezone.utc).isoformat()
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        with self._conn() as conn:
            existing = conn.execute(
                """
                SELECT review_item_id FROM project_schedule_named_baseline_review_items
                WHERE project_key=?
                  AND current_schedule_version_key=?
                  AND comparison_basis=?
                  AND baseline_schedule_version_key=?
                  AND source_stable_key=?
                  AND source_metric_key=?
                  AND source_signal_type=?
                  AND COALESCE(source_activity_id, '') = COALESCE(?, '')
                """,
                (
                    identity.project_key,
                    identity.current_schedule_version_key,
                    identity.comparison_basis,
                    identity.baseline_schedule_version_key,
                    identity.source_stable_key,
                    identity.source_metric_key,
                    identity.source_signal_type,
                    identity.source_activity_id,
                ),
            ).fetchone()
            if existing:
                review_item_id = str(existing["review_item_id"])
                conn.execute(
                    """
                    UPDATE project_schedule_named_baseline_review_items
                    SET item_type=?, item_title=?, priority=?, evidence_json=?,
                        source_activity_id=?, baseline_slot_label=?, baseline_selection_id=?,
                        baseline_schedule_data_date=?, baseline_display_name=?,
                        schedule_data_date=?, as_of_date=?, last_seen_at=?, updated_at=?
                    WHERE review_item_id=?
                    """,
                    (
                        str(candidate.get("item_type") or "cue"),
                        str(candidate.get("item_title") or ""),
                        int(candidate.get("priority") or 50),
                        evidence_json,
                        candidate.get("source_activity_id"),
                        scope.baseline_slot_label,
                        scope.baseline_selection_id,
                        scope.baseline_schedule_data_date,
                        scope.baseline_display_name,
                        scope.schedule_data_date,
                        scope.as_of_date,
                        now,
                        now,
                        review_item_id,
                    ),
                )
                self._append_event(
                    conn,
                    review_item_id=review_item_id,
                    project_key=scope.project_key,
                    current_schedule_version_key=scope.current_schedule_version_key,
                    event_type=EVENT_SYNCED,
                )
            else:
                review_item_id = f"{NAMED_REVIEW_ITEM_ID_PREFIX}{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO project_schedule_named_baseline_review_items (
                      review_item_id, project_key, review_scope, current_schedule_version_key,
                      comparison_basis, baseline_slot_key, baseline_slot_label, baseline_selection_id,
                      baseline_schedule_version_key, baseline_schedule_data_date, baseline_display_name,
                      schedule_data_date, as_of_date, source_stable_key, source_metric_key,
                      source_signal_type, source_activity_id, item_type, item_title, priority,
                      review_status, pm_notes, evidence_json, last_seen_at, created_at, updated_at
                    ) VALUES (?, ?, 'named_baseline', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                    """,
                    (
                        review_item_id,
                        scope.project_key,
                        scope.current_schedule_version_key,
                        scope.comparison_basis,
                        scope.baseline_slot_key,
                        scope.baseline_slot_label,
                        scope.baseline_selection_id,
                        scope.baseline_schedule_version_key,
                        scope.baseline_schedule_data_date,
                        scope.baseline_display_name,
                        scope.schedule_data_date,
                        scope.as_of_date,
                        identity.source_stable_key,
                        identity.source_metric_key,
                        identity.source_signal_type,
                        identity.source_activity_id,
                        str(candidate.get("item_type") or "cue"),
                        str(candidate.get("item_title") or ""),
                        int(candidate.get("priority") or 50),
                        REVIEW_OPEN,
                        evidence_json,
                        now,
                        now,
                        now,
                    ),
                )
                self._append_event(
                    conn,
                    review_item_id=review_item_id,
                    project_key=scope.project_key,
                    current_schedule_version_key=scope.current_schedule_version_key,
                    event_type=EVENT_CREATED,
                    new_status=REVIEW_OPEN,
                )
        row = self.get_review_item(review_item_id=review_item_id)
        return row or {}

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
                "SELECT * FROM project_schedule_named_baseline_review_items WHERE review_item_id=?",
                (review_item_id,),
            ).fetchone()
            if not row:
                return None
            prior_status = str(row["review_status"])
            prior_notes = row["pm_notes"]
            conn.execute(
                """
                UPDATE project_schedule_named_baseline_review_items
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
            updated = conn.execute(
                "SELECT * FROM project_schedule_named_baseline_review_items WHERE review_item_id=?",
                (review_item_id,),
            ).fetchone()
            if review_status is not None and review_status != prior_status:
                self._append_event(
                    conn,
                    review_item_id=review_item_id,
                    project_key=str(row["project_key"]),
                    current_schedule_version_key=str(row["current_schedule_version_key"]),
                    event_type=EVENT_STATUS_CHANGED,
                    prior_status=prior_status,
                    new_status=review_status,
                    operator_id=reviewed_by_operator,
                )
            if pm_notes is not None and pm_notes != prior_notes:
                self._append_event(
                    conn,
                    review_item_id=review_item_id,
                    project_key=str(row["project_key"]),
                    current_schedule_version_key=str(row["current_schedule_version_key"]),
                    event_type=EVENT_NOTES_CHANGED,
                    prior_notes=prior_notes,
                    new_notes=pm_notes,
                    operator_id=reviewed_by_operator,
                )
            conn.commit()
        return self._row(dict(updated)) if updated else None

    def list_review_item_events(
        self,
        *,
        review_item_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM project_schedule_named_baseline_review_item_events
                WHERE review_item_id=?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (review_item_id, max(1, min(limit, 200))),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _identity_from_candidate(
        scope: NamedBaselineReviewScope,
        candidate: dict[str, Any],
    ) -> NamedBaselineReviewIdentity:
        evidence = candidate.get("evidence") or {}
        return NamedBaselineReviewIdentity(
            project_key=scope.project_key,
            current_schedule_version_key=scope.current_schedule_version_key,
            comparison_basis=scope.comparison_basis,
            baseline_schedule_version_key=scope.baseline_schedule_version_key,
            source_stable_key=str(candidate.get("stable_item_key") or ""),
            source_metric_key=str(
                candidate.get("source_metric_key") or evidence.get("source_metric_key") or ""
            ),
            source_signal_type=str(
                candidate.get("source_signal_type") or evidence.get("source_signal_type") or ""
            ),
            source_activity_id=candidate.get("source_activity_id"),
        )

    @staticmethod
    def _append_event(
        conn: sqlite3.Connection,
        *,
        review_item_id: str,
        project_key: str,
        current_schedule_version_key: str,
        event_type: str,
        prior_status: str | None = None,
        new_status: str | None = None,
        prior_notes: str | None = None,
        new_notes: str | None = None,
        operator_id: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO project_schedule_named_baseline_review_item_events (
              event_id, review_item_id, project_key, current_schedule_version_key,
              event_type, prior_status, new_status, prior_notes, new_notes,
              operator_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"psnbre-{uuid.uuid4().hex}",
                review_item_id,
                project_key,
                current_schedule_version_key,
                event_type,
                prior_status,
                new_status,
                prior_notes,
                new_notes,
                operator_id,
                now,
            ),
        )

    @staticmethod
    def _row(row: dict[str, Any]) -> dict[str, Any]:
        evidence_raw = row.get("evidence_json")
        if evidence_raw and isinstance(evidence_raw, str):
            try:
                row["evidence"] = json.loads(evidence_raw)
            except json.JSONDecodeError:
                row["evidence"] = {}
        elif "evidence" not in row:
            row["evidence"] = {}
        row["stable_item_key"] = row.get("source_stable_key")
        row["schedule_version_key"] = row.get("current_schedule_version_key")
        row["review_scope"] = row.get("review_scope") or "named_baseline"
        return row
