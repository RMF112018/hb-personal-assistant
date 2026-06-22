"""Procore activity JSON projection into V62 canonical table."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.analytics.schedule_procore_activity_adapter import (
    project_procore_activity,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository

_ACTIVITY_RAW = {
    "activity_id": "245",
    "activity_name": "Install Windows",
    "start_date": "2024-05-14T13:30:00Z",
    "finish_date": "2024-05-25T17:00:00Z",
    "duration": 5,
    "duration_unit": "day",
    "percent_complete": 75.5,
    "is_critical": True,
    "total_float": 2.5,
    "schedule_id": "15",
    "project_id": "12345",
}


def test_procore_activity_projection_upserts() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "proj.db")
        SQLiteMigrator(db_path=db_path).apply()
        out = project_procore_activity(
            _ACTIVITY_RAW,
            project_key="tropical",
            db_path=db_path,
            parent_schedule_id="15",
            sync_run_id="sync-test-1",
        )
        assert out["status"] == "upserted"
        repo = ScheduleActivityRepository(db_path=db_path)
        acts = repo.list_activities(out["schedule_version_key"])
        assert len(acts) == 1
        assert acts[0]["activity_id"] == "245"
        assert acts[0]["activity_name"] == "Install Windows"
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            """
            SELECT schedule_table_id FROM procore_ep_schedule_activities
            WHERE schedule_version_key=? AND activity_id='245'
            """,
            (out["schedule_version_key"],),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] is not None
        parent = repo.find_schedule_table_id(project_key="tropical", schedule_id="15")
        assert parent == row[0]