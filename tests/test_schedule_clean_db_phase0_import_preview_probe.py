"""Import preview mutation probe tests."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.schedule_clean_db.import_preview_probe import (
    run_import_preview_mutation_probe,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

FIXTURE = Path(__file__).resolve().parents[0] / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"


def test_probe_classifies_db_neutral(tmp_path: Path) -> None:
    db = tmp_path / "probe.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    result = run_import_preview_mutation_probe(
        db, project_key="tropical", fixture_path=FIXTURE
    )
    assert result["classification"] == "db_neutral"
    assert result["commit_executed"] is False
