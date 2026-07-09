"""V115 source-structure schema: migration idempotence, table + index presence, empty ship."""

from __future__ import annotations

import sqlite3

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.source_structure_override_tables import V116_TABLES
from hb_assistant.store.source_structure_tables import V115_TABLES


def _migrate(tmp_path) -> str:
    dbp = str(tmp_path / "pa.db")
    return dbp


def test_latest_schema_version_covers_source_structure():
    # Soft floor, not a moving literal: the V115 source-structure migration must be included. The
    # single deliberate exact-version bump-guard lives in test_n8c_final_validation.py.
    assert LATEST_SCHEMA_VERSION >= 115


def test_migration_applies_and_is_idempotent(tmp_path):
    dbp = _migrate(tmp_path)
    m = SQLiteMigrator(dbp)
    assert m.apply() == LATEST_SCHEMA_VERSION
    # Re-running the migration must be a no-op that still reports the latest version.
    assert m.apply() == LATEST_SCHEMA_VERSION


def test_all_v115_and_v116_tables_exist_and_ship_empty(tmp_path):
    dbp = _migrate(tmp_path)
    SQLiteMigrator(dbp).apply()
    conn = sqlite3.connect(dbp)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in (*V115_TABLES, *V116_TABLES):
            assert t in names, f"missing table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
    finally:
        conn.close()


def test_v115_and_v116_migration_rows_recorded(tmp_path):
    dbp = _migrate(tmp_path)
    SQLiteMigrator(dbp).apply()
    conn = sqlite3.connect(dbp)
    try:
        versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        assert {115, 116} <= versions
    finally:
        conn.close()


def test_folders_indexes_present(tmp_path):
    dbp = _migrate(tmp_path)
    SQLiteMigrator(dbp).apply()
    conn = sqlite3.connect(dbp)
    try:
        idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert any(i.startswith("idx_source_structure_folders_project") for i in idx)
        assert any(i.startswith("idx_source_structure_folders_rank") for i in idx)
        assert any(i.startswith("idx_source_structure_roots_rank") for i in idx)
    finally:
        conn.close()


def test_folder_check_constraints_reject_bad_enum(tmp_path):
    dbp = _migrate(tmp_path)
    SQLiteMigrator(dbp).apply()
    conn = sqlite3.connect(dbp)
    try:
        # folder_class must be a known enum value.
        try:
            conn.execute(
                "INSERT INTO source_structure_folders "
                "(folder_id, root_key, rel_path, name, depth, folder_class, trust_tier, search_rank) "
                "VALUES ('x','r','a','a',1,'not_a_class','high',10)"
            )
            conn.commit()
            raised = False
        except sqlite3.IntegrityError:
            raised = True
        assert raised, "CHECK constraint should reject an unknown folder_class"
    finally:
        conn.close()
