"""Repository for project-level named schedule baseline slot selections."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from hb_assistant.store.connection import open_connection, transaction


class ProjectScheduleNamedBaselineRepository:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def list_active_slots(self, *, project_key: str) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM project_schedule_named_baseline_slots
                WHERE project_key=? AND is_active=1
                ORDER BY slot_key
                """,
                (project_key,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_active_slot(self, *, project_key: str, slot_key: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM project_schedule_named_baseline_slots
                WHERE project_key=? AND slot_key=? AND is_active=1
                ORDER BY selected_at DESC, updated_at DESC
                LIMIT 1
                """,
                (project_key, slot_key),
            ).fetchone()
        return dict(row) if row else None

    def set_slot_selection(
        self,
        *,
        project_key: str,
        slot_key: str,
        schedule_version_key: str,
        display_name: str | None,
        notes: str | None,
        selected_by: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                conn.execute(
                    """
                    UPDATE project_schedule_named_baseline_slots
                    SET is_active=0, updated_at=?
                    WHERE project_key=? AND slot_key=? AND is_active=1
                    """,
                    (now, project_key, slot_key),
                )
                selection_id = f"pnbs-{uuid.uuid4().hex}"
                conn.execute(
                    """
                    INSERT INTO project_schedule_named_baseline_slots (
                      selection_id, project_key, slot_key, schedule_version_key,
                      display_name, notes, selected_by, selected_at,
                      created_at, updated_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        selection_id,
                        project_key,
                        slot_key,
                        schedule_version_key,
                        display_name,
                        notes,
                        selected_by,
                        now,
                        now,
                        now,
                    ),
                )
        return self.get_active_slot(project_key=project_key, slot_key=slot_key) or {}

    def clear_slot(self, *, project_key: str, slot_key: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with open_connection(self._db_path) as conn:
            conn.execute(
                """
                UPDATE project_schedule_named_baseline_slots
                SET is_active=0, updated_at=?
                WHERE project_key=? AND slot_key=? AND is_active=1
                """,
                (now, project_key, slot_key),
            )
            conn.commit()
