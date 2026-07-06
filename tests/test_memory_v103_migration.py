"""V103 memory-compiler migration (N8C-7): additive, idempotent, prior rows survive."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_MEM_TABLES = {
    "assistant_memory_nodes",
    "assistant_memory_mentions",
    "assistant_memory_compilations",
    "assistant_memory_events",
}


def _tables(db: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_head_is_103() -> None:
    assert LATEST_SCHEMA_VERSION == 103


def test_apply_creates_four_memory_tables(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    head = SQLiteMigrator(db_path=db).apply()
    assert head == LATEST_SCHEMA_VERSION
    assert _tables(db) >= _MEM_TABLES


def test_migration_is_idempotent_applied_twice(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    first = SQLiteMigrator(db_path=db).apply()
    second = SQLiteMigrator(db_path=db).apply()
    assert first == second == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 103").fetchone()[0]
    assert rows == 1


def test_prior_v100_v101_v102_rows_remain(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        for ver, name in ((100, "v100_assistant_claims"), (101, "v101_assistant_enrichment"),
                          (102, "v102_assistant_context_packs")):
            row = c.execute("SELECT name FROM schema_migrations WHERE version = ?", (ver,)).fetchone()
            assert row is not None and row[0] == name
    names = _tables(db)
    assert {"assistant_claims", "assistant_enrichment_jobs", "assistant_context_packs"} <= names
