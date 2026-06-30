"""V95 CPM import observability migration: additive, idempotent."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def test_latest_schema_version_is_at_least_95() -> None:
    assert LATEST_SCHEMA_VERSION >= 95


def test_cpm_import_observability_table_created_additive(tmp_path: Path) -> None:
    db = str(tmp_path / "v95.sqlite")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "schedule_cpm_import_observability" in names
    indexes = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='schedule_cpm_import_observability'"
        ).fetchall()
    }
    assert "idx_schedule_cpm_import_obs_import" in indexes


def test_reapply_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "v95.sqlite")
    SQLiteMigrator(db_path=db).apply()
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
