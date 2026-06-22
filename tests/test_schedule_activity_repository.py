"""Schedule activity repository upsert and lineage tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_import_repository import ScheduleImportRepository


def _db(tmp: str) -> str:
    path = Path(tmp) / "repo.db"
    SQLiteMigrator(db_path=str(path)).apply()
    return str(path)


def test_bulk_upsert_and_query_lineage() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        imp = ScheduleImportRepository(db_path=db)
        act = ScheduleActivityRepository(db_path=db)
        imp.insert_import(
            {
                "import_id": "imp1",
                "project_key": "tropical",
                "source_type": "xml",
                "source_format": "primavera_pmxml",
                "import_status": "committed",
                "schedule_version_key": "tropical|S1|2026-06-01",
            }
        )
        act.bulk_upsert_activities(
            [
                {
                    "project_key": "tropical",
                    "schedule_id": "S1",
                    "schedule_version_key": "tropical|S1|2026-06-01",
                    "import_id": "imp1",
                    "source_type": "xml",
                    "source_format": "primavera_pmxml",
                    "activity_id": "A1",
                    "activity_name": "Task One",
                    "start_date": "2026-01-01",
                    "finish_date": "2026-01-31",
                }
            ]
        )
        rows = act.list_activities("tropical|S1|2026-06-01")
        assert len(rows) == 1
        assert rows[0]["activity_id"] == "A1"
        assert act.count_activities("tropical|S1|2026-06-01") == 1