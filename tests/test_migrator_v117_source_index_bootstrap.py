"""V117 source-index bootstrap + reconciliation migration: additive, idempotent, CHECK-guarded.

Scratch DBs only (``tmp_path``); no live/production DB is touched.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def test_latest_schema_version_is_at_least_117() -> None:
    assert LATEST_SCHEMA_VERSION >= 117


def test_v117_tables_created_additive(tmp_path: Path) -> None:
    db = str(tmp_path / "v117.sqlite")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"source_index_bootstrap_state", "source_index_reconciliation_runs"} <= names
    # additive: the reused source-intelligence + structure tables must still be present.
    for prior in (
        "source_intelligence_sources",
        "source_intelligence_events",
        "source_intelligence_state",
        "source_structure_roots",
        "source_structure_runs",
    ):
        assert prior in names, prior


def test_bootstrap_state_columns(tmp_path: Path) -> None:
    db = str(tmp_path / "v117.sqlite")
    SQLiteMigrator(db_path=db).apply()
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(source_index_bootstrap_state)")}
    assert {
        "root_key",
        "file_index_bootstrapped",
        "file_index_last_success_at",
        "structure_index_bootstrapped",
        "watcher_ready",
        "last_error",
    } <= cols
    # boolean CHECK enforced
    con.execute("INSERT INTO source_index_bootstrap_state(root_key) VALUES ('r1')")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO source_index_bootstrap_state(root_key, watcher_ready) VALUES ('r2', 2)"
        )


def test_reconciliation_scan_type_check(tmp_path: Path) -> None:
    db = str(tmp_path / "v117.sqlite")
    SQLiteMigrator(db_path=db).apply()
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO source_index_reconciliation_runs(run_id, root_key, scan_type) "
        "VALUES ('run1', 'r1', 'lightweight')"
    )
    con.execute(
        "INSERT INTO source_index_reconciliation_runs(run_id, root_key, scan_type) "
        "VALUES ('run2', 'r1', 'full')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO source_index_reconciliation_runs(run_id, root_key, scan_type) "
            "VALUES ('run3', 'r1', 'bogus')"
        )


def test_reapply_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "v117.sqlite")
    SQLiteMigrator(db_path=db).apply()
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION


def test_old_db_upgrades_to_117(tmp_path: Path) -> None:
    # Simulate an older DB stopped at 116, then upgrade: the v117 block must apply cleanly on top.
    db = str(tmp_path / "upgrade.sqlite")
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)"
    )
    con.commit()
    con.close()
    # A real apply() rebuilds from v1 forward; the guard is that reaching head includes 117.
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    con = sqlite3.connect(db)
    row = con.execute("SELECT name FROM schema_migrations WHERE version = 117").fetchone()
    assert row is not None and row[0] == "v117_source_index_bootstrap"
