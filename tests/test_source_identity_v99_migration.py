"""V99 source-identity root-scoping (NAS N8).

Covers the live derivation (source_root_key folded into source_id), same-root idempotency,
cross-root distinctness, and the one-time migration/backfill that remaps existing colliding
file source_ids across every FK'd table.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from hb_assistant.obsidian_mcp.source_index_repository import (
    SourceIndexRepository,
    source_id_for,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _old_file_sid(source_kind: str, rel_path: str) -> str:
    """Pre-V99 root-blind derivation (source_kind|file|rel_path)."""
    return hashlib.sha256(f"{source_kind}|file|{rel_path}".encode()).hexdigest()[:32]


def test_latest_schema_version_is_106() -> None:
    # v99 folded root_key into source_id; v100 (N8C-4) claim-extraction; v101 (N8C-5) enrichment
    # queue; v102 (N8C-6) context packs; v103 (N8C-7) memory-compiler tables; v104 (N8C-8)
    # decision/preference/open-loop memory tables; v105 (N8C-9) review-overlay tables; v106 (N8C-10)
    # added the review-aware intelligence-projection tables.
    assert LATEST_SCHEMA_VERSION == 106


def test_source_id_folds_in_root_key() -> None:
    a = source_id_for("external_file", source_root_key="home", rel_path="shared/x.txt")
    b = source_id_for("external_file", source_root_key="work", rel_path="shared/x.txt")
    assert a != b
    # domain-link identity unchanged (no root component)
    link = source_id_for("obsidian_note", domain_ref_table="t", domain_ref_id="1")
    assert link == hashlib.sha256(b"obsidian_note|link|t|1").hexdigest()[:32]


def test_same_root_upsert_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = SourceIndexRepository(db)
    rec = {"source_kind": "external_file", "source_root_key": "work", "rel_path": "a/b.txt",
           "content_sha256": "deadbeef"}
    sid1 = repo.upsert_source_file(dict(rec))
    sid2 = repo.upsert_source_file(dict(rec))
    assert sid1 == sid2
    with sqlite3.connect(db) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM source_intelligence_sources "
            "WHERE source_kind='external_file' AND rel_path='a/b.txt'"
        ).fetchone()[0]
    assert n == 1


def test_distinct_roots_same_relpath_coexist(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = SourceIndexRepository(db)
    sid_home = repo.upsert_source_file(
        {"source_kind": "external_file", "source_root_key": "home", "rel_path": "shared/x.txt"})
    sid_work = repo.upsert_source_file(
        {"source_kind": "external_file", "source_root_key": "work", "rel_path": "shared/x.txt"})
    assert sid_home != sid_work
    # both rows survive (no cross-root overwrite), each keyed to its own root
    look_home = repo.lookup_by_path("external_file", "shared/x.txt", source_root_key="home")
    look_work = repo.lookup_by_path("external_file", "shared/x.txt", source_root_key="work")
    assert look_home is not None and look_home["source_id"] == sid_home
    assert look_work is not None and look_work["source_id"] == sid_work


def test_v99_migration_remaps_old_colliding_ids_and_children(tmp_path: Path) -> None:
    """Simulate a pre-V99 file row (root-blind id + children), run the reconcile, and prove the
    id is remapped root-scoped across sources/metadata/generated_notes with FK integrity intact."""
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()  # schema already at v99

    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("BEGIN")
        # Revert to the pre-V99 index shape and seed an old-id row + FK'd children.
        conn.execute("DROP INDEX IF EXISTS idx_si_sources_root_relpath")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_si_sources_relpath "
            "ON source_intelligence_sources(source_kind, rel_path) WHERE rel_path IS NOT NULL"
        )
        old_id = _old_file_sid("external_file", "shared/x.txt")
        conn.execute(
            "INSERT INTO source_intelligence_sources "
            "(source_id, source_kind, source_root_key, rel_path, active, deleted) "
            "VALUES (?, 'external_file', 'work', 'shared/x.txt', 1, 0)", (old_id,))
        conn.execute(
            "INSERT INTO source_intelligence_metadata (source_id, extraction_status) "
            "VALUES (?, 'pending')", (old_id,))
        conn.execute(
            "INSERT INTO source_intelligence_generated_notes "
            "(generated_note_id, source_id, note_rel_path, generation_status) "
            "VALUES ('gn1', ?, 'Source Notes/x.md', 'generated')", (old_id,))

        SQLiteMigrator._reconcile_v99_source_identity_root_scoped(conn)
        conn.commit()  # raises if the deferred FK graph is inconsistent

        new_id = source_id_for("external_file", source_root_key="work", rel_path="shared/x.txt")
        assert new_id != old_id
        assert conn.execute(
            "SELECT source_id FROM source_intelligence_sources WHERE rel_path='shared/x.txt'"
        ).fetchone()[0] == new_id
        assert conn.execute(
            "SELECT source_id FROM source_intelligence_metadata"
        ).fetchone()[0] == new_id
        assert conn.execute(
            "SELECT source_id FROM source_intelligence_generated_notes WHERE generated_note_id='gn1'"
        ).fetchone()[0] == new_id
        assert conn.execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE source_id=?", (old_id,)
        ).fetchone()[0] == 0
        idx = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='source_intelligence_sources'")}
        assert "idx_si_sources_root_relpath" in idx
        assert "idx_si_sources_relpath" not in idx
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_v99_migration_is_noop_when_already_root_scoped(tmp_path: Path) -> None:
    """A DB freshly migrated to v99 has root-scoped ids already; re-running the reconcile changes
    nothing (idempotent) and leaves row ids stable."""
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    repo = SourceIndexRepository(db)
    sid = repo.upsert_source_file(
        {"source_kind": "external_file", "source_root_key": "work", "rel_path": "a/b.txt"})
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("BEGIN")
        SQLiteMigrator._reconcile_v99_source_identity_root_scoped(conn)
        conn.commit()
        assert conn.execute(
            "SELECT source_id FROM source_intelligence_sources WHERE rel_path='a/b.txt'"
        ).fetchone()[0] == sid
    finally:
        conn.close()
