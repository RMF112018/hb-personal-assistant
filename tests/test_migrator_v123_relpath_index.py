"""V123: drop the redundant narrow rel_path unique index (source_kind, rel_path).

That index omitted source_root_key, so it wrongly rejected the SAME rel_path under two different roots
(e.g. "Altman/…" under both `work` and `syn-work`) — blocking multi-root source indexing. The root-scoped
idx_si_sources_root_relpath already enforces correct per-root uniqueness.

Scratch DBs only.
"""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _indexes(db: str, table: str = "source_intelligence_sources") -> set[str]:
    c = sqlite3.connect(db)
    try:
        return {
            r[0]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name=?",
                (table,),
            )
        }
    finally:
        c.close()


def test_v123_is_latest_and_fresh_db_has_only_root_scoped_index(tmp_path):
    db = str(tmp_path / "fresh.db")
    SQLiteMigrator(db_path=db).apply()
    idx = _indexes(db)
    assert LATEST_SCHEMA_VERSION >= 123
    # V128 moves current-path uniqueness to the locator authority.
    assert "idx_si_sources_root_relpath" not in idx
    assert "idx_locators_active_path" in _indexes(db, "source_index_locators")
    assert "idx_si_sources_relpath" not in idx  # narrow index never present on a fresh V123 DB
    c = sqlite3.connect(db)
    assert c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] >= 123
    c.close()


def test_v123_drops_a_pre_existing_narrow_index(tmp_path):
    db = str(tmp_path / "old.db")
    SQLiteMigrator(db_path=db).apply()
    # Simulate a DB migrated before this fix: the historical narrow index is present and V123 unrecorded.
    c = sqlite3.connect(db)
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_si_sources_relpath "
        "ON source_intelligence_sources(source_kind, rel_path) WHERE rel_path IS NOT NULL"
    )
    c.execute("DELETE FROM schema_migrations WHERE version=123")
    c.commit()
    c.close()
    assert "idx_si_sources_relpath" in _indexes(db)  # precondition: narrow index present
    # Re-run migrations → V123 drops it (idempotent, index-only).
    SQLiteMigrator(db_path=db).apply()
    idx = _indexes(db)
    assert "idx_si_sources_relpath" not in idx
    assert "idx_si_sources_root_relpath" not in idx
    assert "idx_locators_active_path" in _indexes(db, "source_index_locators")


def test_same_relpath_under_two_roots_coexists_after_v123(tmp_path):
    db = str(tmp_path / "roots.db")
    SQLiteMigrator(db_path=db).apply()
    rel = "Altman/Altman Box Backup/00-100 - AGC PM SOP/file.pdf"
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    repo = SourceIndexRepository(db)
    repo.upsert_source_file({
        "source_kind": "external_file", "source_root_key": "work", "rel_path": rel,
    })
    repo.upsert_source_file({
        "source_kind": "external_file", "source_root_key": "syn-work", "rel_path": rel,
    })
    c = sqlite3.connect(db)
    n = c.execute(
        "SELECT count(*) FROM source_intelligence_sources WHERE rel_path=?", (rel,)
    ).fetchone()[0]
    assert n == 2  # both roots coexist (the narrow index would have rejected the second)
    # The repository is idempotent for a true duplicate current path.
    before = c.execute(
        "SELECT count(*) FROM source_index_locators "
        "WHERE source_root_key='work' AND rel_path=? AND is_current_locator=1",
        (rel,),
    ).fetchone()[0]
    repo.upsert_source_file({
        "source_kind": "external_file", "source_root_key": "work", "rel_path": rel,
    })
    after = c.execute(
        "SELECT count(*) FROM source_index_locators "
        "WHERE source_root_key='work' AND rel_path=? AND is_current_locator=1",
        (rel,),
    ).fetchone()[0]
    assert before == after == 1
    # V129 locator authority still enforces one active entity per root/path at the DB boundary.
    c.execute(
        "INSERT INTO source_index_entities(source_entity_id, created_at, status) "
        "VALUES ('duplicate-path-entity', 't', 'LIVE')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(
            "INSERT INTO source_index_locators("
            "locator_id, source_entity_id, source_id, source_root_key, rel_path, "
            "is_current_locator, tombstoned_at, generation_seq"
            ") VALUES ('duplicate-path-locator', 'duplicate-path-entity', 'duplicate-path-source', "
            "'work', ?, 1, NULL, 0)",
            (rel,),
        )
    c.rollback()
    c.close()


def test_migration_is_idempotent_on_rerun(tmp_path):
    db = str(tmp_path / "idem.db")
    assert SQLiteMigrator(db_path=db).apply() >= 123
    assert SQLiteMigrator(db_path=db).apply() >= 123  # second run must not raise
    assert "idx_si_sources_relpath" not in _indexes(db)
