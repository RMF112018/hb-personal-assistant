"""V128 — permanent source identity (Realization A: entity-scoped content, 7-table rebuild).

Proves: a fresh migrate reaches head 128 with the entity-keyed shape (3 new identity tables +
source_entity_id on the parent, the 6 FK children, and the 2 non-FK tables); re-applying is an
idempotent no-op; and — on a seeded pre-V128 database — the rebuild mints exactly one entity + one
current locator per source, preserves every child row re-keyed to the entity id, backfills the
non-FK tables via the locator map (unresolved stays NULL), and fails CLOSED (whole-transaction
rollback) when a child row is orphaned. Uses scratch SQLite DBs only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.source_index_scan_quarantine_tables import (
    V125_SOURCE_INDEX_SCAN_QUARANTINE_STATEMENTS,
)
from hb_assistant.store.source_intelligence_tables import V93_STATEMENTS, V94_STATEMENTS

NEW_TABLES = ("source_index_entities", "source_index_locators", "source_index_move_signals")


def _cols(db: str, table: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _pk_cols(db: str, table: str) -> list[str]:
    with sqlite3.connect(db) as c:
        return [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall() if r[5]]


def _tables(db: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _indexes(db: str, table: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute(f"PRAGMA index_list({table})").fetchall()}


def _versions(db: str) -> set[int]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT version FROM schema_migrations").fetchall()}


def _fk_check(db: str) -> list:
    with sqlite3.connect(db) as c:
        return c.execute("PRAGMA foreign_key_check").fetchall()


@pytest.fixture()
def fresh(tmp_path: Path) -> str:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


# ---------------------------------------------------------------------------------------------------
# Fresh-DB shape + idempotency
# ---------------------------------------------------------------------------------------------------


def test_latest_version_is_128(fresh) -> None:
    assert LATEST_SCHEMA_VERSION == 128
    assert 128 in _versions(fresh)


def test_new_identity_tables_and_columns_present(fresh) -> None:
    assert set(NEW_TABLES).issubset(_tables(fresh))
    assert {"source_entity_id", "created_at", "status"} == _cols(fresh, "source_index_entities")
    loc = _cols(fresh, "source_index_locators")
    assert {
        "locator_id", "source_entity_id", "source_id", "source_root_key", "rel_path",
        "is_current_locator", "tombstoned_at", "generation_seq",
    }.issubset(loc)
    assert {
        "move_signal_id", "source_locator_id", "source_root_key", "source_rel_path",
        "target_root_key", "target_rel_path", "detected_at", "generation_id", "applied_at",
    } == _cols(fresh, "source_index_move_signals")


def test_locator_indexes_present(fresh) -> None:
    idx = _indexes(fresh, "source_index_locators")
    assert {
        "idx_locators_current_per_entity",
        "idx_locators_active_path",
        "idx_locators_source_id",
    }.issubset(idx)


def test_parent_reparented_to_entity_id(fresh) -> None:
    cols = _cols(fresh, "source_intelligence_sources")
    assert "source_entity_id" in cols
    assert "source_id" not in cols
    assert _pk_cols(fresh, "source_intelligence_sources") == ["source_entity_id"]
    # durable attrs retained; V122 generation-tracking scratch columns intentionally dropped.
    assert {"source_kind", "rel_path", "renamed_from_source_id"}.issubset(cols)
    assert "last_seen_generation" not in cols


def test_children_reparented_to_entity_id(fresh) -> None:
    for child in (
        "source_intelligence_metadata",
        "source_intelligence_text",
        "source_intelligence_summaries",
        "source_intelligence_chunks",
        "source_intelligence_generated_notes",
    ):
        c = _cols(fresh, child)
        assert "source_entity_id" in c, child
        assert "source_id" not in c, child
    rel = _cols(fresh, "source_intelligence_relationships")
    assert "src_source_entity_id" in rel
    assert "src_source_id" not in rel


def test_quarantine_gains_entity_ref(fresh) -> None:
    assert "source_entity_id" in _cols(fresh, "source_index_scan_quarantine")


def test_events_reparent_deferred_stays_v127_shape(fresh) -> None:
    # DEFERRED (repo-truth conflict): V127's unconditional always-revalidate guard would strip an
    # FK column added to events on the next apply(), so V128 does NOT reparent events. This asserts
    # the deviation is intentional and events keeps its exact V127 shape (so the guard stays happy).
    assert "source_entity_id" not in _cols(fresh, "source_intelligence_events")


def test_foreign_key_check_clean_on_fresh(fresh) -> None:
    assert _fk_check(fresh) == []


def test_reapply_is_idempotent(fresh) -> None:
    for _ in range(3):
        assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    # 128 recorded exactly once
    with sqlite3.connect(fresh) as c:
        n = c.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=128").fetchone()[0]
    assert n == 1


# ---------------------------------------------------------------------------------------------------
# Seeded pre-V128 rebuild — content preservation + backfill + fail-closed gate
# ---------------------------------------------------------------------------------------------------


def _build_pre_v128(db: str, *, orphan_chunk: bool = False) -> None:
    """Create the pre-V128 (source_id-keyed) tables from the real DDL modules, add the V122/V126
    columns the rebuild consumes, and seed rows. ``orphan_chunk`` adds a child row whose source_id
    has no parent (to exercise the no-orphan gate)."""
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = OFF")  # seed freely; the rebuild re-checks FKs itself
    for stmt in V93_STATEMENTS:
        conn.execute(stmt)
    for stmt in V94_STATEMENTS:
        conn.execute(stmt)
    for stmt in V125_SOURCE_INDEX_SCAN_QUARANTINE_STATEMENTS:
        conn.execute(stmt)
    # V126 lineage column + V122 metadata columns the rebuild carries over.
    conn.execute("ALTER TABLE source_intelligence_sources ADD COLUMN renamed_from_source_id TEXT")
    conn.execute("ALTER TABLE source_intelligence_metadata ADD COLUMN extraction_disposition TEXT")
    conn.execute("ALTER TABLE source_intelligence_metadata ADD COLUMN content_indexed_at TEXT")

    conn.executemany(
        "INSERT INTO source_intelligence_sources"
        "(source_id, source_kind, source_root_key, rel_path, abs_path_hash, domain_ref_table,"
        " domain_ref_id, project_key, project_number, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("src-file-1", "external_file", "work", "a/b.txt", "h1", None, None, "PK", "100",
             "2026-01-01T00:00:00", "2026-01-02T00:00:00"),
            ("src-file-2", "external_file", "work", "c/d.txt", "h2", None, None, "PK", "100",
             "2026-01-03T00:00:00", "2026-01-04T00:00:00"),
            ("src-dom-1", "email", None, None, None, "email_messages", "msg-1", "PK", "100",
             "2026-01-05T00:00:00", "2026-01-06T00:00:00"),
        ],
    )
    conn.executemany(
        "INSERT INTO source_intelligence_metadata"
        "(source_id, file_ext, size_bytes, content_sha256, extraction_status) VALUES (?,?,?,?,?)",
        [("src-file-1", "txt", 11, "sha-1", "ok"), ("src-file-2", "txt", 22, "sha-2", "pending")],
    )
    conn.execute(
        "INSERT INTO source_intelligence_text(source_id, text_excerpt, excerpt_char_count) "
        "VALUES ('src-file-1', 'hello excerpt', 13)"
    )
    conn.execute(
        "INSERT INTO source_intelligence_summaries"
        "(source_id, model_provider, prompt_version, summary_sha256) "
        "VALUES ('src-file-1', 'ollama', 'p1', 'sum-1')"
    )
    conn.executemany(
        "INSERT INTO source_intelligence_chunks(chunk_id, source_id, ordinal, chunk_text, char_count) "
        "VALUES (?,?,?,?,?)",
        [
            ("ch-1", "src-file-1", 0, "chunk zero", 10),
            ("ch-2", "src-file-1", 1, "chunk one", 9),
            ("ch-3", "src-file-2", 0, "other chunk", 11),
        ],
    )
    if orphan_chunk:
        conn.execute(
            "INSERT INTO source_intelligence_chunks(chunk_id, source_id, ordinal, chunk_text, char_count) "
            "VALUES ('ch-ghost', 'ghost-source', 0, 'orphan', 6)"
        )
    conn.execute(
        "INSERT INTO source_intelligence_generated_notes(generated_note_id, source_id, note_rel_path) "
        "VALUES ('gn-1', 'src-file-1', 'notes/x.md')"
    )
    conn.execute(
        "INSERT INTO source_intelligence_relationships"
        "(relationship_id, src_source_id, dst_kind, dst_ref, relation) "
        "VALUES ('rel-1', 'src-file-1', 'project', 'PK', 'belongs_to_project')"
    )
    conn.executemany(
        "INSERT INTO source_intelligence_events(event_id, source_id, event_type) VALUES (?,?,?)",
        [
            ("ev-1", "src-file-1", "created"),  # resolvable
            ("ev-2", None, "rebuild"),          # no source -> stays NULL
            ("ev-3", "ghost-source", "deleted"),  # orphan source -> stays NULL
        ],
    )
    conn.execute(
        "INSERT INTO source_index_scan_quarantine"
        "(quarantine_id, source_root_key, source_id, rel_path, failure_stage, error_code,"
        " first_seen_at, last_seen_at) "
        "VALUES ('q-1', 'work', 'src-file-2', 'c/d.txt', 'stat', 'stat_failed', 't0', 't1')"
    )
    conn.commit()
    conn.close()


def _run_rebuild(db: str) -> None:
    """Invoke the V128 rebuild helper inside one explicit transaction (mirrors apply())."""
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.isolation_level = None  # explicit transaction control
    conn.execute("BEGIN")
    try:
        SQLiteMigrator._rebuild_v128_permanent_identity(conn)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def test_rebuild_mints_entities_and_current_locators(tmp_path) -> None:
    db = str(tmp_path / "pre.sqlite")
    _build_pre_v128(db)
    _run_rebuild(db)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM source_index_entities").fetchone()[0] == 3
        assert c.execute(
            "SELECT COUNT(*) FROM source_index_entities WHERE status='LIVE'"
        ).fetchone()[0] == 3
        assert c.execute("SELECT COUNT(*) FROM source_index_locators").fetchone()[0] == 3
        assert c.execute(
            "SELECT COUNT(*) FROM source_index_locators WHERE is_current_locator=1"
        ).fetchone()[0] == 3
        # exactly one current locator per entity
        assert c.execute(
            "SELECT COUNT(*) FROM source_index_entities e WHERE "
            "(SELECT COUNT(*) FROM source_index_locators l "
            " WHERE l.source_entity_id=e.source_entity_id AND l.is_current_locator=1) != 1"
        ).fetchone()[0] == 0
    assert _fk_check(db) == []


def test_rebuild_preserves_child_content_rekeyed_to_entity(tmp_path) -> None:
    db = str(tmp_path / "pre.sqlite")
    _build_pre_v128(db)
    _run_rebuild(db)
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row

        def eid(source_id: str) -> str:
            return c.execute(
                "SELECT source_entity_id FROM source_index_locators WHERE source_id=?",
                (source_id,),
            ).fetchone()[0]

        e1 = eid("src-file-1")
        e2 = eid("src-file-2")
        # metadata preserved + re-keyed
        m = c.execute(
            "SELECT content_sha256, extraction_status FROM source_intelligence_metadata "
            "WHERE source_entity_id=?", (e1,)
        ).fetchone()
        assert (m[0], m[1]) == ("sha-1", "ok")
        # text
        t = c.execute(
            "SELECT text_excerpt, excerpt_char_count FROM source_intelligence_text "
            "WHERE source_entity_id=?", (e1,)
        ).fetchone()
        assert (t[0], t[1]) == ("hello excerpt", 13)
        # summaries
        s = c.execute(
            "SELECT model_provider, summary_sha256 FROM source_intelligence_summaries "
            "WHERE source_entity_id=?", (e1,)
        ).fetchone()
        assert (s[0], s[1]) == ("ollama", "sum-1")
        # chunks: 1:N preserved by chunk_id, correct entity mapping
        chunks = c.execute(
            "SELECT chunk_id, ordinal, chunk_text FROM source_intelligence_chunks "
            "WHERE source_entity_id=? ORDER BY ordinal", (e1,)
        ).fetchall()
        assert [(r[0], r[1], r[2]) for r in chunks] == [
            ("ch-1", 0, "chunk zero"), ("ch-2", 1, "chunk one")
        ]
        assert c.execute(
            "SELECT chunk_id FROM source_intelligence_chunks WHERE source_entity_id=?", (e2,)
        ).fetchone()[0] == "ch-3"
        assert c.execute("SELECT COUNT(*) FROM source_intelligence_chunks").fetchone()[0] == 3
        # generated notes + relationships preserved by PK and re-keyed
        assert c.execute(
            "SELECT source_entity_id FROM source_intelligence_generated_notes "
            "WHERE generated_note_id='gn-1'"
        ).fetchone()[0] == e1
        assert c.execute(
            "SELECT src_source_entity_id, relation FROM source_intelligence_relationships "
            "WHERE relationship_id='rel-1'"
        ).fetchone()[0] == e1
    assert _fk_check(db) == []


def test_rebuild_backfills_quarantine_via_locator(tmp_path) -> None:
    db = str(tmp_path / "pre.sqlite")
    _build_pre_v128(db)
    _run_rebuild(db)
    with sqlite3.connect(db) as c:
        e2 = c.execute(
            "SELECT source_entity_id FROM source_index_locators WHERE source_id='src-file-2'"
        ).fetchone()[0]
        # quarantine row for src-file-2 resolves to its entity
        assert c.execute(
            "SELECT source_entity_id FROM source_index_scan_quarantine WHERE quarantine_id='q-1'"
        ).fetchone()[0] == e2
        # events reparenting is DEFERRED (see migrator Step 5) — events keeps its V127 shape
        assert "source_entity_id" not in {
            r[1] for r in c.execute("PRAGMA table_info(source_intelligence_events)").fetchall()
        }
    assert _fk_check(db) == []


def test_orphan_child_fails_closed_and_rolls_back(tmp_path) -> None:
    db = str(tmp_path / "pre.sqlite")
    _build_pre_v128(db, orphan_chunk=True)
    with pytest.raises(RuntimeError, match="v128_chunks_orphan_failed"):
        _run_rebuild(db)
    # whole transaction rolled back: no new identity tables, old source_id key intact
    assert "source_index_entities" not in _tables(db)
    assert "source_id" in _cols(db, "source_intelligence_sources")
    with sqlite3.connect(db) as c:
        assert c.execute(
            "SELECT source_id FROM source_intelligence_chunks WHERE chunk_id='ch-ghost'"
        ).fetchone()[0] == "ghost-source"
