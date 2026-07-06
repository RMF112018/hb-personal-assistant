"""V102 context-pack migration (N8C-6): additive, idempotent, prior rows survive."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_CTX_TABLES = {
    "assistant_context_packs",
    "assistant_context_pack_items",
    "assistant_context_pack_receipts",
    "assistant_context_pack_events",
}


def _tables(db: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_head_is_102() -> None:
    assert LATEST_SCHEMA_VERSION == 102


def test_apply_creates_four_context_pack_tables(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    head = SQLiteMigrator(db_path=db).apply()
    assert head == LATEST_SCHEMA_VERSION
    assert _CTX_TABLES <= _tables(db)


def test_migration_is_idempotent_applied_twice(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    first = SQLiteMigrator(db_path=db).apply()
    second = SQLiteMigrator(db_path=db).apply()
    assert first == second == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 102").fetchone()[0]
    assert rows == 1  # exactly one v102 row after two applies


def test_prior_v100_v101_rows_remain(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        v100 = c.execute("SELECT name FROM schema_migrations WHERE version = 100").fetchone()
        v101 = c.execute("SELECT name FROM schema_migrations WHERE version = 101").fetchone()
    assert v100 is not None and v100[0] == "v100_assistant_claims"
    assert v101 is not None and v101[0] == "v101_assistant_enrichment"
    names = _tables(db)
    assert {"assistant_claims", "assistant_enrichment_jobs", "assistant_enrichment_receipts"} <= names
