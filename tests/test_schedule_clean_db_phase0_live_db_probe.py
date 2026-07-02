"""Live DB unchanged probe tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.schedule_clean_db.live_db_probe import (
    compare_snapshots,
    snapshot_live_db,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "live-probe.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    _seed_comparable_versions(db)
    return db


def test_unchanged_counts_pass(tmp_path: Path) -> None:
    db = _db(tmp_path)
    before = snapshot_live_db(db, project_key="tropical", read_only_live=True)
    after = snapshot_live_db(db, project_key="tropical", read_only_live=True)
    result = compare_snapshots(before, after)
    assert result["passed"] is True


def test_changed_schedule_count_fails(tmp_path: Path) -> None:
    db = _db(tmp_path)
    before = snapshot_live_db(db, project_key="tropical", read_only_live=True)
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM schedule_file_imports WHERE project_key='tropical'")
        conn.commit()
    after = snapshot_live_db(db, project_key="tropical", read_only_live=True)
    result = compare_snapshots(before, after)
    assert result["passed"] is False
    assert result["schedule_count_changes"]


def test_missing_optional_table_does_not_crash(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"
    SQLiteMigrator(db_path=str(db)).apply()
    snap = snapshot_live_db(db, project_key="tropical", read_only_live=True)
    assert "schedule_table_counts" in snap
