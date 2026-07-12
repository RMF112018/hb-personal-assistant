"""Phase B / B4 — V126 additive rename-lineage migration.

Proves ``renamed_from_source_id`` is added additively/nullably to source_intelligence_sources, the
migration is idempotent and parity-guarded (safe on a partially-migrated DB), and V122–V125 are
preserved. Uses scratch SQLite DBs only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _cols(db: str, table: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _versions(db: str) -> set[int]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT version FROM schema_migrations").fetchall()}


def test_latest_version_is_126() -> None:
    assert LATEST_SCHEMA_VERSION == 126


def test_column_and_index_added(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    assert "renamed_from_source_id" in _cols(db, "source_intelligence_sources")
    with sqlite3.connect(db) as c:
        idx = {r[1] for r in c.execute("PRAGMA index_list(source_intelligence_sources)").fetchall()}
    assert "idx_si_sources_renamed_from" in idx
    # column is nullable (legacy rows carry no predecessor)
    with sqlite3.connect(db) as c:
        info = {r[1]: r for r in c.execute("PRAGMA table_info(source_intelligence_sources)").fetchall()}
    assert info["renamed_from_source_id"][3] == 0  # notnull flag == 0


def test_preserves_prior_source_index_versions(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    assert {122, 123, 124, 125, 126} <= _versions(db)


def test_idempotent_reapply(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # A second full apply must not raise (all migrations guarded / IF NOT EXISTS / parity ADD COLUMN).
    SQLiteMigrator(db_path=db).apply()
    assert "renamed_from_source_id" in _cols(db, "source_intelligence_sources")


def test_parity_guard_on_partially_migrated_db(tmp_path: Path) -> None:
    # Simulate a partial state: migrated DB with the V126 marker removed but the column already present.
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        c.execute("DELETE FROM schema_migrations WHERE version = 126")
        c.commit()
    # Re-apply: the parity guard must skip the ALTER (column exists) rather than raise duplicate-column.
    SQLiteMigrator(db_path=db).apply()
    assert 126 in _versions(db)
    assert "renamed_from_source_id" in _cols(db, "source_intelligence_sources")
