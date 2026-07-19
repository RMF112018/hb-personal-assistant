"""V128 — permanent source identity (Realization A: entity-scoped content, 7-table rebuild).

Proves: a fresh migrate reaches head 128 with the entity-keyed shape (3 new identity tables +
source_entity_id on the parent, the 6 FK children, and the 2 non-FK tables); re-applying is an
idempotent no-op; and — on a seeded pre-V128 database — the rebuild mints exactly one entity + one
current locator per source, preserves every child row re-keyed to the entity id, backfills the
non-FK tables via the locator map (unresolved stays NULL), and fails CLOSED (whole-transaction
rollback) when a child row is orphaned. Uses scratch SQLite DBs only.
"""

from __future__ import annotations

import dataclasses
import shutil
import sqlite3
import threading
from pathlib import Path

import pytest

from hb_assistant.store import migrator as migrator_module
from hb_assistant.store.migrator import (
    LATEST_SCHEMA_VERSION,
    SQLiteMigrator,
    V128OracleError,
    get_connection,
)
from hb_assistant.store.source_index_scan_quarantine_tables import (
    V125_SOURCE_INDEX_SCAN_QUARANTINE_STATEMENTS,
)
from hb_assistant.store.source_intelligence_tables import (
    EVENT_STATUS_VALUES,
    EVENT_TYPE_VALUES_V127,
    V93_STATEMENTS,
    V94_STATEMENTS,
)

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


def _fk_list(db: str, table: str) -> list:
    with sqlite3.connect(db) as c:
        return c.execute(f"PRAGMA foreign_key_list({table})").fetchall()


def test_events_reparented_with_entity_fk(fresh) -> None:
    # IMP-F-002: V128 now reparents events durably — a nullable source_entity_id FK to
    # source_index_entities plus its index. V127's always-revalidate guard was extended to tolerate
    # and preserve it, so the column survives repeated apply() (see test_events_fk_persists_...).
    assert "source_entity_id" in _cols(fresh, "source_intelligence_events")
    assert "idx_si_events_entity" in _indexes(fresh, "source_intelligence_events")
    fks = _fk_list(fresh, "source_intelligence_events")
    assert len(fks) == 1
    assert (fks[0][2], fks[0][3], fks[0][4]) == (
        "source_index_entities", "source_entity_id", "source_entity_id"
    )


def test_events_fk_persists_across_two_applies(fresh) -> None:
    # IMP-F-002 acceptance: apply twice; the entity FK column must still be present (not stripped by
    # the V127 always-revalidate rebuild).
    assert "source_entity_id" in _cols(fresh, "source_intelligence_events")
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "source_entity_id" in _cols(fresh, "source_intelligence_events")
    assert "idx_si_events_entity" in _indexes(fresh, "source_intelligence_events")
    assert _fk_check(fresh) == []


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


def test_rebuild_backfills_quarantine_and_events_via_locator(tmp_path) -> None:
    db = str(tmp_path / "pre.sqlite")
    _build_pre_v128(db)
    _run_rebuild(db)
    with sqlite3.connect(db) as c:
        def eid(source_id: str) -> str:
            return c.execute(
                "SELECT source_entity_id FROM source_index_locators WHERE source_id=?",
                (source_id,),
            ).fetchone()[0]

        e2 = eid("src-file-2")
        # quarantine row for src-file-2 resolves to its entity
        assert c.execute(
            "SELECT source_entity_id FROM source_index_scan_quarantine WHERE quarantine_id='q-1'"
        ).fetchone()[0] == e2
        # IMP-F-002: events reparented via the locator map. ev-1 (src-file-1) resolves; ev-2 (no
        # source) and ev-3 (orphan source) stay NULL.
        assert "source_entity_id" in {
            r[1] for r in c.execute("PRAGMA table_info(source_intelligence_events)").fetchall()
        }
        e1 = eid("src-file-1")
        assert c.execute(
            "SELECT source_entity_id FROM source_intelligence_events WHERE event_id='ev-1'"
        ).fetchone()[0] == e1
        assert c.execute(
            "SELECT source_entity_id FROM source_intelligence_events WHERE event_id='ev-2'"
        ).fetchone()[0] is None
        assert c.execute(
            "SELECT source_entity_id FROM source_intelligence_events WHERE event_id='ev-3'"
        ).fetchone()[0] is None
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


# ---------------------------------------------------------------------------------------------------
# Corrective findings — REV-F-001 (NOT NULL keys), REV-F-003 (parent CHECK), REV-F-002 (always-
# revalidate / drift repair), IMP-F-003 (same-path reuse after tombstone + self-heal)
# ---------------------------------------------------------------------------------------------------


def test_null_identity_key_rejected(fresh) -> None:
    # REV-F-001: a NULL source_entity_id must be rejected on the identity table, the parent, and the
    # 1:1 children (TEXT PRIMARY KEY otherwise permits NULL in SQLite).
    with sqlite3.connect(fresh) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO source_index_entities(source_entity_id, created_at, status) "
                "VALUES (NULL, 't', 'LIVE')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO source_intelligence_sources(source_entity_id, source_kind, rel_path) "
                "VALUES (NULL, 'external_file', 'p/q.txt')"
            )
        for child in (
            "source_intelligence_metadata",
            "source_intelligence_text",
            "source_intelligence_summaries",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                c.execute(f"INSERT INTO {child}(source_entity_id) VALUES (NULL)")


def test_parent_pathless_domainless_rejected(fresh) -> None:
    # REV-F-003: the restored parent CHECK requires either a rel_path or a full domain reference.
    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = ON")
        c.execute(
            "INSERT INTO source_index_entities(source_entity_id, created_at, status) "
            "VALUES ('e-chk', 't', 'LIVE')"
        )
        # pathless + domainless -> CHECK violation
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO source_intelligence_sources(source_entity_id, source_kind) "
                "VALUES ('e-chk', 'external_file')"
            )
        # a row WITH rel_path is accepted
        c.execute(
            "INSERT INTO source_intelligence_sources(source_entity_id, source_kind, rel_path) "
            "VALUES ('e-chk', 'external_file', 'ok/path.txt')"
        )


def test_v128_schema_current_true_on_fresh(fresh) -> None:
    from hb_assistant.store.migrator import get_connection

    c = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(c) is True
    finally:
        c.close()


def test_drift_dropped_move_signals_is_repaired(fresh) -> None:
    # REV-F-002: a dropped identity table is detected (not trusted on version-record) and repaired.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("DROP TABLE source_index_move_signals")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "source_index_move_signals" in _tables(fresh)
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is True
    finally:
        gc.close()


def test_drift_dropped_locator_index_is_repaired(fresh) -> None:
    # REV-F-002: a dropped required locator index is detected and repaired.
    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_locators_active_path")
    assert "idx_locators_active_path" not in _indexes(fresh, "source_index_locators")
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "idx_locators_active_path" in _indexes(fresh, "source_index_locators")


def test_drift_obsolete_parent_index_is_dropped(fresh) -> None:
    # REV-F-002 + IMP-F-003: a re-created obsolete parent path-unique index is detected and dropped.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute(
            "CREATE UNIQUE INDEX idx_si_sources_root_relpath "
            "ON source_intelligence_sources(source_kind, source_root_key, rel_path) "
            "WHERE rel_path IS NOT NULL"
        )
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "idx_si_sources_root_relpath" not in _indexes(fresh, "source_intelligence_sources")


def test_drift_wrong_column_locator_index_is_rejected_and_repaired(fresh) -> None:
    # REV-F-002 (CP-PI-WI-02-R2): a required locator index with the correct NAME but the WRONG
    # indexed column must be detected (not accepted on name alone) and repaired to the right columns.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_locators_current_per_entity")
        # same name, wrong indexed column (source_id instead of source_entity_id)
        c.execute(
            "CREATE INDEX idx_locators_current_per_entity "
            "ON source_index_locators(source_id)"
        )

    def _idx_cols(db: str, idx: str) -> list[str]:
        with sqlite3.connect(db) as c:
            return [r[2] for r in c.execute(f"PRAGMA index_info({idx})").fetchall()]

    assert _idx_cols(fresh, "idx_locators_current_per_entity") == ["source_id"]
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False  # NOT accepted on name alone
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    # repaired to the correct indexed column
    assert _idx_cols(fresh, "idx_locators_current_per_entity") == ["source_entity_id"]


def test_drift_child_without_notnull_or_fk_fails_closed(fresh) -> None:
    # REV-F-002 (CP-PI-WI-02-R2): a child source_entity_id column with no NOT NULL and no FK must be
    # rejected by _v128_schema_current and fail closed on apply() (a non-additively-repairable drift),
    # never silently accepted (which previously let the weakened child take a NULL identity).
    import pytest

    from hb_assistant.store.migrator import get_connection

    # Rebuild source_intelligence_metadata (1:1) keeping ALL real columns but dropping the NOT NULL +
    # FK on source_entity_id (CREATE TABLE ... AS SELECT copies data with no constraints/keys/FKs).
    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("ALTER TABLE source_intelligence_metadata RENAME TO _md_old")
        c.execute("CREATE TABLE source_intelligence_metadata AS SELECT * FROM _md_old")
        c.execute("DROP TABLE _md_old")
    # sanity: the entity column is now NULL-able and FK-less
    _md = {r[1]: r[3] for r in sqlite3.connect(fresh).execute(
        "PRAGMA table_info(source_intelligence_metadata)")}
    assert _md.get("source_entity_id") == 0  # notnull == 0 (weakened)

    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    # apply() cannot additively repair a malformed child -> fail closed, transaction rolled back.
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


# --- CP-PI-WI-02-R3: the oracle is a COMPLETE structural contract -------------------------------
# Each of the following drifts keeps enough of the shape that the pre-R3 name/column/notnull-only
# oracle would have returned True (accepting a malformed V128 DB). The completed oracle rejects them;
# repairable drifts (index uniqueness/partial predicate, non-FK entity refs) are repaired on apply();
# non-repairable table-level drifts (a lost PK/FK/CHECK) fail closed rather than being trusted.


def _idx_flags(db: str, table: str, name: str) -> tuple[int, int] | None:
    with sqlite3.connect(db) as c:
        for r in c.execute(f"PRAGMA index_list({table})").fetchall():
            if r[1] == name:
                return (int(r[2]), int(r[4]))  # (unique, partial)
    return None


def test_drift_nonunique_locator_index_rejected_and_repaired(fresh) -> None:
    # Right name + right column + right partial predicate, but NOT UNIQUE -> rejected, then repaired.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_locators_current_per_entity")
        c.execute(
            "CREATE INDEX idx_locators_current_per_entity "
            "ON source_index_locators(source_entity_id) WHERE is_current_locator=1"
        )
    assert _idx_flags(fresh, "source_index_locators", "idx_locators_current_per_entity") == (0, 1)
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert _idx_flags(fresh, "source_index_locators", "idx_locators_current_per_entity") == (1, 1)


def test_drift_locator_index_missing_partial_predicate_rejected_and_repaired(fresh) -> None:
    # Right name + columns + UNIQUE, but the partial WHERE predicate is gone -> rejected, then repaired.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_locators_active_path")
        c.execute(
            "CREATE UNIQUE INDEX idx_locators_active_path "
            "ON source_index_locators(source_root_key, rel_path)"
        )
    assert _idx_flags(fresh, "source_index_locators", "idx_locators_active_path") == (1, 0)
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert _idx_flags(fresh, "source_index_locators", "idx_locators_active_path") == (1, 1)


def test_drift_1to1_child_pk_loss_fails_closed(fresh) -> None:
    # A 1:1 child that KEEPS NOT NULL + FK on source_entity_id but LOSES its PRIMARY KEY. The pre-R3
    # oracle only checked notnull + FK, so it accepted this; the completed oracle rejects on pk, and
    # the drift is not additively repairable -> fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP TABLE source_intelligence_metadata")
        c.execute(
            "CREATE TABLE source_intelligence_metadata ("
            " source_entity_id TEXT NOT NULL"
            " REFERENCES source_index_entities(source_entity_id),"  # NOT NULL + FK kept, PK dropped
            " file_ext TEXT, size_bytes INTEGER, mtime_ns INTEGER, content_sha256 TEXT,"
            " page_count INTEGER, paragraph_count INTEGER, sheet_count INTEGER,"
            " extraction_status TEXT NOT NULL DEFAULT 'pending',"
            " extraction_failure_code TEXT, fts_rowid INTEGER,"
            " indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " extraction_disposition TEXT, content_indexed_at TEXT)"
        )
    # sanity: entity column is NOT NULL + FK, but no longer a primary key
    _md = {r[1]: (int(r[3]), int(r[5])) for r in sqlite3.connect(fresh).execute(
        "PRAGMA table_info(source_intelligence_metadata)")}
    assert _md["source_entity_id"] == (1, 0)  # notnull=1, pk=0
    assert _fk_list(fresh, "source_intelligence_metadata")  # FK still present
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


def _recreate_parent(db: str, *, with_fk: bool, with_addr_check: bool) -> None:
    fk = " REFERENCES source_index_entities(source_entity_id)" if with_fk else ""
    addr = (
        ", CHECK((rel_path IS NOT NULL)"
        " OR (domain_ref_table IS NOT NULL AND domain_ref_id IS NOT NULL))"
        if with_addr_check else ""
    )
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP TABLE source_intelligence_sources")
        c.execute(
            "CREATE TABLE source_intelligence_sources ("
            f" source_entity_id TEXT NOT NULL PRIMARY KEY{fk},"
            " source_kind TEXT NOT NULL CHECK(source_kind IN ('external_file')),"
            " source_root_key TEXT, rel_path TEXT, abs_path_hash TEXT,"
            " domain_ref_table TEXT, domain_ref_id TEXT, project_key TEXT, project_number TEXT,"
            " active INTEGER NOT NULL DEFAULT 1, deleted INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            f" renamed_from_source_id TEXT{addr})"
        )


def test_drift_parent_missing_addressability_check_fails_closed(fresh) -> None:
    # Parent keeps entity PK + authority FK but LOSES the rel_path-or-domain CHECK -> rejected + fail closed.
    from hb_assistant.store.migrator import get_connection

    _recreate_parent(fresh, with_fk=True, with_addr_check=False)
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_parent_missing_authority_fk_fails_closed(fresh) -> None:
    # Parent keeps entity PK + addressability CHECK but LOSES the authority FK -> rejected + fail closed.
    from hb_assistant.store.migrator import get_connection

    _recreate_parent(fresh, with_fk=False, with_addr_check=True)
    assert not _fk_list(fresh, "source_intelligence_sources")  # FK gone
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_locators_table_stripped_fails_closed(fresh) -> None:
    # The locators table loses its own keys/constraints (rebuilt via AS SELECT drops PK/NOT NULL/FK).
    # Additive repair re-creates the INDEXES but never rebuilds the table -> rejected + fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("ALTER TABLE source_index_locators RENAME TO _loc_old")
        c.execute("CREATE TABLE source_index_locators AS SELECT * FROM _loc_old")
        c.execute("DROP TABLE _loc_old")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_move_signals_pk_loss_fails_closed(fresh) -> None:
    # move_signals loses its move_signal_id PRIMARY KEY (rebuilt via AS SELECT). The additive repair
    # only re-creates the table when it is ABSENT, so a present-but-malformed table -> fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("ALTER TABLE source_index_move_signals RENAME TO _ms_old")
        c.execute("CREATE TABLE source_index_move_signals AS SELECT * FROM _ms_old")
        c.execute("DROP TABLE _ms_old")
    _ms = {r[1]: int(r[5]) for r in sqlite3.connect(fresh).execute(
        "PRAGMA table_info(source_index_move_signals)")}
    assert _ms["move_signal_id"] == 0  # pk lost
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_events_missing_entity_ref_rejected_and_repaired(fresh) -> None:
    # The events table exists but its nullable source_entity_id entity ref is gone -> rejected, then
    # repaired (the non-FK reparent step re-adds the column + FK) on apply().
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP INDEX IF EXISTS idx_si_events_entity")
        c.execute("ALTER TABLE source_intelligence_events DROP COLUMN source_entity_id")
    assert "source_entity_id" not in _cols(fresh, "source_intelligence_events")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "source_entity_id" in _cols(fresh, "source_intelligence_events")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is True
    finally:
        gc.close()


# --- CP-PI-WI-02-R4: the oracle is a GENUINELY complete contract --------------------------------
# Each drift keeps enough that the R5 (partial-enumeration) oracle returned True: a compound index
# predicate with one conjunct dropped, a payload table stripped to its key columns, a move-signal
# table stripped to its PK, a parent CHECK weakened to domain-only, and a fully-absent non-FK table.
# The complete oracle rejects all five (repairable index drift is repaired on apply(); the rest fail
# closed).


def test_drift_active_path_predicate_incomplete_rejected_and_repaired(fresh) -> None:
    # idx_locators_active_path keeps its name+columns+UNIQUE but drops the is_current_locator=1
    # conjunct of its compound partial predicate -> rejected, then repaired to the full predicate.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_locators_active_path")
        c.execute("CREATE UNIQUE INDEX idx_locators_active_path "
                  "ON source_index_locators(source_root_key, rel_path) WHERE tombstoned_at IS NULL")

    def _pred(db: str, idx: str) -> str:
        with sqlite3.connect(db) as c:
            row = c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
                            (idx,)).fetchone()
        return " ".join((row[0] or "").split()) if row and row[0] else ""

    assert "is_current_locator=1" not in _pred(fresh, "idx_locators_active_path")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "is_current_locator=1 AND tombstoned_at IS NULL" in _pred(fresh, "idx_locators_active_path")


def test_drift_payload_columns_stripped_fails_closed(fresh) -> None:
    # A 1:1 child that keeps its entity PK + FK but is stripped of every payload column -> rejected
    # (full column set enforced) and not additively repairable -> fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP TABLE source_intelligence_metadata")
        c.execute("CREATE TABLE source_intelligence_metadata ("
                  " source_entity_id TEXT NOT NULL PRIMARY KEY"
                  " REFERENCES source_index_entities(source_entity_id))")
    # sanity: entity key/PK/FK intact, payload columns gone
    _md = _cols(fresh, "source_intelligence_metadata")
    assert _md == {"source_entity_id"}
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False  # complete oracle rejects it
    finally:
        gc.close()
    # Fail closed: apply() must not silently record 128. Stripping the payload also trips an earlier
    # migration statement referencing a now-missing column, so the fail-closed surfaces as an
    # OperationalError rather than v128_schema_parity_failed — either way the whole transaction rolls
    # back and the malformed shape is never accepted (the pre-R4 oracle accepted it silently).
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_move_signals_columns_stripped_fails_closed(fresh) -> None:
    # move_signals keeps only its PRIMARY KEY column -> rejected (full column set enforced) and the
    # additive repair only re-creates the table when ABSENT -> present-but-stripped fails closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("DROP TABLE source_index_move_signals")
        c.execute("CREATE TABLE source_index_move_signals (move_signal_id TEXT PRIMARY KEY)")
    assert _cols(fresh, "source_index_move_signals") == {"move_signal_id"}
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_parent_check_weakened_to_domain_only_fails_closed(fresh) -> None:
    # Parent keeps entity PK + authority FK + source_kind CHECK, but the addressability CHECK is
    # weakened to domain-only (drops the rel_path OR branch) -> rejected (full CHECK clause enforced)
    # and not additively repairable -> fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP TABLE source_intelligence_sources")
        c.execute("CREATE TABLE source_intelligence_sources ("
                  " source_entity_id TEXT NOT NULL PRIMARY KEY"
                  " REFERENCES source_index_entities(source_entity_id),"
                  " source_kind TEXT NOT NULL CHECK(source_kind IN ('external_file')),"
                  " source_root_key TEXT, rel_path TEXT, abs_path_hash TEXT,"
                  " domain_ref_table TEXT, domain_ref_id TEXT, project_key TEXT, project_number TEXT,"
                  " active INTEGER NOT NULL DEFAULT 1, deleted INTEGER NOT NULL DEFAULT 0,"
                  " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                  " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                  " renamed_from_source_id TEXT,"
                  " CHECK(domain_ref_table IS NOT NULL AND domain_ref_id IS NOT NULL))")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_events_table_absent_is_rejected_and_repaired(fresh) -> None:
    # The non-FK events table is now MANDATORY in the oracle: its absence (or a missing entity index)
    # is rejected. On apply() the V127 events always-revalidate re-creates the table and the V128
    # reparent re-adds its nullable entity ref + index, so the drift is healed (repairable).
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP INDEX IF EXISTS idx_si_events_entity")
        c.execute("DROP TABLE source_intelligence_events")
    assert "source_intelligence_events" not in _tables(fresh)
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "source_intelligence_events" in _tables(fresh)
    assert "source_entity_id" in _cols(fresh, "source_intelligence_events")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is True
    finally:
        gc.close()


# --- CP-PI-WI-02-R5: reference-schema comparison (complete by construction) ----------------------
# The oracle now validates a live DB by exact-equality against the canonical V128 schema (built once
# from a fresh scratch migrate). These drifts are the R5 residuals the hand-enumerated oracle missed:
# a dropped supporting index, an events entity index on the wrong column, an extra column, a changed
# FK action, and a changed column default. All are now detected; a dropped supporting index is
# repaired, the rest fail closed.


def test_drift_dropped_supporting_index_rejected_and_repaired(fresh) -> None:
    # A supporting index (the UNIQUE idx_si_sources_domain) removed -> detected, then repaired by
    # _v128_ensure_supporting_indexes on apply().
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_si_sources_domain")
    assert "idx_si_sources_domain" not in _indexes(fresh, "source_intelligence_sources")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "idx_si_sources_domain" in _indexes(fresh, "source_intelligence_sources")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is True
    finally:
        gc.close()


def test_drift_events_entity_index_wrong_column_rejected_and_repaired(fresh) -> None:
    # The events entity index recreated on the WRONG column -> detected by index-column check (the
    # hand-enumerated oracle checked it by name only). Repaired on apply() (the V127 events rebuild
    # reconstructs the table + its correct indexes), restoring idx_si_events_entity to source_entity_id.
    from hb_assistant.store.migrator import get_connection

    def _idx_cols(db: str, idx: str) -> list[str]:
        with sqlite3.connect(db) as c:
            return [r[2] for r in c.execute(f"PRAGMA index_info({idx})").fetchall()]

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP INDEX idx_si_events_entity")
        c.execute("CREATE INDEX idx_si_events_entity ON source_intelligence_events(event_id)")
    assert _idx_cols(fresh, "idx_si_events_entity") == ["event_id"]
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False  # detected by column, not name
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert _idx_cols(fresh, "idx_si_events_entity") == ["source_entity_id"]  # repaired
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is True
    finally:
        gc.close()


def test_drift_extra_column_rejected_and_fails_closed(fresh) -> None:
    # An unexpected extra column on a V128 table -> detected (strict parity; the operator-selected
    # resolution of the additive-tolerance scope question) and not additively repairable -> fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("ALTER TABLE source_index_entities ADD COLUMN spurious TEXT")
    assert "spurious" in _cols(fresh, "source_index_entities")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_fk_on_delete_cascade_rejected(fresh) -> None:
    # The entity FK changed to ON DELETE CASCADE (materially different integrity behavior) -> detected
    # (the hand-enumerated oracle's _fks ignored on_delete). Not repairable -> fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP TABLE source_intelligence_metadata")
        c.execute("CREATE TABLE source_intelligence_metadata ("
                  " source_entity_id TEXT NOT NULL PRIMARY KEY REFERENCES"
                  " source_index_entities(source_entity_id) ON DELETE CASCADE,"
                  " file_ext TEXT, size_bytes INTEGER, mtime_ns INTEGER, content_sha256 TEXT,"
                  " page_count INTEGER, paragraph_count INTEGER, sheet_count INTEGER,"
                  " extraction_status TEXT NOT NULL DEFAULT 'pending',"
                  " extraction_failure_code TEXT, fts_rowid INTEGER,"
                  " indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                  " extraction_disposition TEXT, content_indexed_at TEXT)")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()


def test_drift_changed_column_default_rejected(fresh) -> None:
    # A changed column DEFAULT (active DEFAULT 1 -> DEFAULT 0) -> detected (the hand-enumerated oracle
    # never inspected defaults). Not repairable -> fail closed.
    from hb_assistant.store.migrator import get_connection

    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("DROP TABLE source_intelligence_sources")
        c.execute("CREATE TABLE source_intelligence_sources ("
                  " source_entity_id TEXT NOT NULL PRIMARY KEY"
                  " REFERENCES source_index_entities(source_entity_id),"
                  " source_kind TEXT NOT NULL CHECK(source_kind IN ('external_file')),"
                  " source_root_key TEXT, rel_path TEXT, abs_path_hash TEXT,"
                  " domain_ref_table TEXT, domain_ref_id TEXT, project_key TEXT, project_number TEXT,"
                  " active INTEGER NOT NULL DEFAULT 0, deleted INTEGER NOT NULL DEFAULT 0,"  # active default flipped
                  " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                  " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                  " renamed_from_source_id TEXT,"
                  " CHECK((rel_path IS NOT NULL)"
                  " OR (domain_ref_table IS NOT NULL AND domain_ref_id IS NOT NULL)))")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()


def _seed_entity_at_path(
    db: str, *, eid: str, sid: str, root: str, rel: str, current: bool
) -> None:
    """Insert an entity + parent source + locator at (root, rel)."""
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys = ON")
        c.execute(
            "INSERT INTO source_index_entities(source_entity_id, created_at, status) "
            "VALUES (?, 't', 'LIVE')", (eid,)
        )
        c.execute(
            "INSERT INTO source_intelligence_sources"
            "(source_entity_id, source_kind, source_root_key, rel_path) VALUES (?,?,?,?)",
            (eid, "external_file", root, rel),
        )
        c.execute(
            "INSERT INTO source_index_locators"
            "(locator_id, source_entity_id, source_id, source_root_key, rel_path, "
            " is_current_locator, tombstoned_at, generation_seq) VALUES (?,?,?,?,?,?,?,0)",
            ("loc-" + eid, eid, sid, root, rel, 1 if current else 0, None if current else "t"),
        )


def _tombstone(db: str, eid: str) -> None:
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys = ON")
        c.execute(
            "UPDATE source_index_entities SET status='TOMBSTONED' WHERE source_entity_id=?", (eid,)
        )
        c.execute(
            "UPDATE source_index_locators SET is_current_locator=0, tombstoned_at='t' "
            "WHERE source_entity_id=?", (eid,)
        )


def test_same_path_reuse_after_tombstone(fresh) -> None:
    # IMP-F-003: after tombstoning an entity at a path, a NEW entity may reuse the SAME path.
    _seed_entity_at_path(fresh, eid="E1", sid="s1", root="work", rel="reuse/x.txt", current=True)
    _tombstone(fresh, "E1")
    # New entity at the same path must succeed (no obsolete parent unique index blocks it, and the
    # active-path locator uniqueness only covers current + non-tombstoned rows).
    _seed_entity_at_path(fresh, eid="E2", sid="s2", root="work", rel="reuse/x.txt", current=True)
    with sqlite3.connect(fresh) as c:
        n = c.execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE rel_path='reuse/x.txt'"
        ).fetchone()[0]
    assert n == 2
    assert _fk_check(fresh) == []


def test_same_path_reuse_after_self_heal(fresh) -> None:
    # IMP-F-003: even after a self-heal (schema_migrations reset to a stale version) re-creates the
    # obsolete parent path-unique index via additive V123, the V128 always-revalidate drops it, so
    # same-path reuse still works.
    _seed_entity_at_path(fresh, eid="E1", sid="s1", root="work", rel="reuse/y.txt", current=True)
    # Simulate self-heal: reset schema_migrations to before V123 (the block that re-creates the
    # obsolete index) and re-apply the whole chain.
    with sqlite3.connect(fresh) as c:
        c.execute("DELETE FROM schema_migrations WHERE version >= 123")
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert "idx_si_sources_root_relpath" not in _indexes(fresh, "source_intelligence_sources")
    _tombstone(fresh, "E1")
    _seed_entity_at_path(fresh, eid="E2", sid="s2", root="work", rel="reuse/y.txt", current=True)
    with sqlite3.connect(fresh) as c:
        n = c.execute(
            "SELECT COUNT(*) FROM source_intelligence_sources WHERE rel_path='reuse/y.txt'"
        ).fetchone()[0]
    assert n == 2
    assert _fk_check(fresh) == []


# ===================================================================================================
# CP-PI-WI-02-R8: reference-derived non-FK contract oracle + connection-bound single-flight reference.
# Additive coverage for the plan §D table-specific repair/fail-closed matrix (events + scan_quarantine)
# on the two non-FK tables, plus the concurrency / immutability / atomic-build machinery (§B, §C).
# ===================================================================================================

_REF = "REFERENCES source_index_entities(source_entity_id)"


@pytest.fixture(autouse=True)
def _v128_reset_build_barrier():
    """R9-PR-F-005: reset the process-wide V128 build BARRIER before and after every test. The build
    barrier is the only stateful test HOOK, so resetting it keeps a machinery test from poisoning a
    later one (order-independence). This fixture does NOT reset ``_V128_REFERENCE``: the reference
    cache is intentionally built-once and reused across tests (a persistent valid reference is
    order-safe and rebuilding it per test would rebuild it ~91x and slow the suite); the machinery
    tests that exercise cache behavior keep their own EXPLICIT ``_V128_REFERENCE = None`` resets.
    Never runs while a builder is active — tests are sequential and no builder survives a test."""
    migrator_module._V128_BUILD_BARRIER = None
    yield
    migrator_module._V128_BUILD_BARRIER = None


def _current(db: str) -> bool:
    """Evaluate the V128 oracle on ``db`` via a real ``get_connection`` (matches production)."""
    c = get_connection(db)
    try:
        return SQLiteMigrator._v128_schema_current(c)
    finally:
        c.close()


def _events_checks() -> tuple[str, str]:
    et = ", ".join(f"'{v}'" for v in EVENT_TYPE_VALUES_V127)
    st = ", ".join(f"'{v}'" for v in EVENT_STATUS_VALUES)
    return (f"CHECK(event_type IN ({et}))", f"CHECK(status IN ({st}))")


def _recreate_events(
    db: str, *, entity_col: str, table_constraints: str = "",
    entity_index: str | None = "CREATE INDEX idx_si_events_entity "
    "ON source_intelligence_events(source_entity_id)",
    extra_indexes: tuple[str, ...] = (),
) -> None:
    """Drop + recreate source_intelligence_events with the full canonical V127 column set (so the V127
    always-revalidate probe passes unless the drift is in V127's contract) plus a customizable
    ``source_entity_id`` column definition / table constraints / entity index."""
    et_check, st_check = _events_checks()
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("DROP TABLE source_intelligence_events")
        c.execute(
            "CREATE TABLE source_intelligence_events ("
            " event_id TEXT PRIMARY KEY, source_id TEXT, rel_path TEXT, source_root_key TEXT,"
            " dest_rel_path TEXT, next_attempt_at TEXT,"
            f" event_type TEXT NOT NULL {et_check},"
            f" status TEXT NOT NULL DEFAULT 'queued' {st_check},"
            " error_code TEXT, attempts INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            f" {entity_col}{table_constraints})"
        )
        c.execute("CREATE INDEX idx_si_events_status ON source_intelligence_events(status, created_at)")
        c.execute("CREATE INDEX idx_si_events_source ON source_intelligence_events(source_id)")
        if entity_index:
            c.execute(entity_index)
        for stmt in extra_indexes:
            c.execute(stmt)


def _recreate_quarantine(
    db: str, *, entity_col: str, table_constraints: str = "",
    entity_index: str | None = "CREATE INDEX idx_si_scan_quarantine_entity "
    "ON source_index_scan_quarantine(source_entity_id)",
    extra_indexes: tuple[str, ...] = (),
) -> None:
    """Drop + recreate source_index_scan_quarantine with its full V125 column set plus a customizable
    ``source_entity_id`` column definition / table constraints / entity index."""
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("DROP TABLE source_index_scan_quarantine")
        c.execute(
            "CREATE TABLE source_index_scan_quarantine ("
            " quarantine_id TEXT PRIMARY KEY, source_root_key TEXT NOT NULL, generation_id TEXT,"
            " origin_generation_id TEXT, source_id TEXT, rel_path TEXT NOT NULL,"
            " failure_stage TEXT NOT NULL, error_code TEXT NOT NULL,"
            " attempt_count INTEGER NOT NULL DEFAULT 0, first_seen_at TEXT NOT NULL,"
            " last_seen_at TEXT NOT NULL, last_attempt_at TEXT,"
            " status TEXT NOT NULL DEFAULT 'quarantined',"
            " resolution_state TEXT NOT NULL DEFAULT 'unresolved', resolved_at TEXT,"
            " last_successful_observation_at TEXT,"
            f" {entity_col}{table_constraints})"
        )
        if entity_index:
            c.execute(entity_index)
        for stmt in extra_indexes:
            c.execute(stmt)


def _insert_events_keep_row(db: str) -> None:
    # source_entity_id is set explicitly NULL (not left to a possibly-drifted column DEFAULT) so it is
    # supplied by the reparent locator backfill, not a bad default that could not be re-keyed.
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute(
            "INSERT INTO source_intelligence_events"
            "(event_id, source_id, source_entity_id, event_type, status) "
            "VALUES ('keep-ev', 's1', NULL, 'created', 'queued')"
        )


def _insert_quarantine_keep_row(db: str) -> None:
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute(
            "INSERT INTO source_index_scan_quarantine"
            "(quarantine_id, source_root_key, source_id, source_entity_id, rel_path, failure_stage,"
            " error_code, first_seen_at, last_seen_at) "
            "VALUES ('keep-q', 'work', 's1', NULL, 'rp/keep.txt', 'stat', 'stat_failed', 't0', 't1')"
        )


def _keep_entity_id(db: str, table: str, pk_col: str, pk_val: str) -> object:
    with sqlite3.connect(db) as c:
        row = c.execute(
            f"SELECT source_entity_id FROM {table} WHERE {pk_col}=?", (pk_val,)
        ).fetchone()
    return row[0] if row else "__row_absent__"


# --- Repair matrix cells: current() is False, apply() heals to LATEST + True, row preserved ---------


def _seed_e1_for_backfill(fresh: str) -> None:
    """Seed one entity/source/current-locator at source_id='s1' so a non-FK row with source_id='s1'
    backfills to entity 'E1' through the reparent locator map."""
    _seed_entity_at_path(fresh, eid="E1", sid="s1", root="work", rel="rp/keep.txt", current=True)


_REPAIR_EVENTS: list[tuple] = [
    # (id, entity_col, table_constraints, entity_index_override_or_default, extra_indexes)
    ("events_wrong_column_index", f"source_entity_id TEXT {_REF}", "",
     "CREATE INDEX idx_si_events_entity ON source_intelligence_events(event_id)", ()),
    ("events_unique_index", f"source_entity_id TEXT {_REF}", "",
     "CREATE UNIQUE INDEX idx_si_events_entity ON source_intelligence_events(source_entity_id)", ()),
    ("events_partial_index", f"source_entity_id TEXT {_REF}", "",
     "CREATE INDEX idx_si_events_entity ON source_intelligence_events(source_entity_id) "
     "WHERE source_entity_id IS NOT NULL", ()),
    ("events_column_integer_default", f"source_entity_id INTEGER DEFAULT 7 {_REF}", "",
     "CREATE INDEX idx_si_events_entity ON source_intelligence_events(source_entity_id)", ()),
    ("events_composite_fk", "source_entity_id TEXT",
     ", FOREIGN KEY(source_entity_id, source_id) "
     "REFERENCES source_index_entities(source_entity_id, created_at)",
     "CREATE INDEX idx_si_events_entity ON source_intelligence_events(source_entity_id)", ()),
    ("events_two_separate_fks", f"source_entity_id TEXT {_REF}",
     f", FOREIGN KEY(source_entity_id) {_REF}",
     "CREATE INDEX idx_si_events_entity ON source_intelligence_events(source_entity_id)", ()),
    ("events_correct_plus_duplicate_fk", f"source_entity_id TEXT {_REF}",
     f", FOREIGN KEY(source_entity_id) {_REF}",
     "CREATE INDEX idx_si_events_entity ON source_intelligence_events(source_entity_id)", ()),
]


@pytest.mark.parametrize(
    "case_id, entity_col, table_constraints, entity_index, extra_indexes",
    _REPAIR_EVENTS, ids=[c[0] for c in _REPAIR_EVENTS],
)
def test_r8_events_drift_repaired(
    fresh, case_id, entity_col, table_constraints, entity_index, extra_indexes
) -> None:
    _seed_e1_for_backfill(fresh)
    _recreate_events(
        fresh, entity_col=entity_col, table_constraints=table_constraints,
        entity_index=entity_index, extra_indexes=extra_indexes,
    )
    _insert_events_keep_row(fresh)
    assert _current(fresh) is False
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert _current(fresh) is True
    # row preserved and backfilled to the seeded entity through the locator map.
    assert _keep_entity_id(fresh, "source_intelligence_events", "event_id", "keep-ev") == "E1"
    assert _fk_check(fresh) == []


_REPAIR_QUARANTINE: list[tuple] = [
    ("quarantine_wrong_column_index", f"source_entity_id TEXT {_REF}", "",
     "CREATE INDEX idx_si_scan_quarantine_entity "
     "ON source_index_scan_quarantine(quarantine_id)", ()),
    ("quarantine_unique_index", f"source_entity_id TEXT {_REF}", "",
     "CREATE UNIQUE INDEX idx_si_scan_quarantine_entity "
     "ON source_index_scan_quarantine(source_entity_id)", ()),
    ("quarantine_partial_index", f"source_entity_id TEXT {_REF}", "",
     "CREATE INDEX idx_si_scan_quarantine_entity "
     "ON source_index_scan_quarantine(source_entity_id) WHERE source_entity_id IS NOT NULL", ()),
]


@pytest.mark.parametrize(
    "case_id, entity_col, table_constraints, entity_index, extra_indexes",
    _REPAIR_QUARANTINE, ids=[c[0] for c in _REPAIR_QUARANTINE],
)
def test_r8_quarantine_drift_repaired(
    fresh, case_id, entity_col, table_constraints, entity_index, extra_indexes
) -> None:
    _seed_e1_for_backfill(fresh)
    _recreate_quarantine(
        fresh, entity_col=entity_col, table_constraints=table_constraints,
        entity_index=entity_index, extra_indexes=extra_indexes,
    )
    _insert_quarantine_keep_row(fresh)
    assert _current(fresh) is False
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert _current(fresh) is True
    assert _keep_entity_id(fresh, "source_index_scan_quarantine", "quarantine_id", "keep-q") == "E1"
    assert _fk_check(fresh) == []


# --- Fail-closed matrix cells: current() is False, apply() raises, rollback preserves schema + data -


_FAIL_EVENTS: list[tuple] = [
    ("events_fk_on_delete_cascade",
     f"source_entity_id TEXT {_REF} ON DELETE CASCADE", "", None),
    ("events_fk_deferrable_initially_deferred",
     f"source_entity_id TEXT {_REF} DEFERRABLE INITIALLY DEFERRED", "", None),
    ("events_fk_deferrable_initially_immediate",
     f"source_entity_id TEXT {_REF} DEFERRABLE INITIALLY IMMEDIATE", "", None),
    ("events_table_level_fk_same_endpoint",
     "source_entity_id TEXT", f", FOREIGN KEY(source_entity_id) {_REF}", None),
    ("events_extra_entity_index", f"source_entity_id TEXT {_REF}", "",
     ("CREATE INDEX idx_ev_extra_entity ON source_intelligence_events(source_entity_id)",)),
    ("events_expression_entity_index", f"source_entity_id TEXT {_REF}", "",
     ("CREATE INDEX idx_ev_expr_entity ON source_intelligence_events((source_entity_id || ''))",)),
]


@pytest.mark.parametrize(
    "case_id, entity_col, table_constraints, extra_indexes",
    _FAIL_EVENTS, ids=[c[0] for c in _FAIL_EVENTS],
)
def test_r8_events_drift_fails_closed(
    fresh, case_id, entity_col, table_constraints, extra_indexes
) -> None:
    _recreate_events(
        fresh, entity_col=entity_col, table_constraints=table_constraints,
        extra_indexes=extra_indexes or (),
    )
    _insert_events_keep_row(fresh)
    assert _current(fresh) is False
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()
    # rollback preserved the drift + the seeded row.
    assert _current(fresh) is False
    assert _keep_entity_id(fresh, "source_intelligence_events", "event_id", "keep-ev") != "__row_absent__"


_FAIL_QUARANTINE: list[tuple] = [
    ("quarantine_fk_on_delete_cascade",
     f"source_entity_id TEXT {_REF} ON DELETE CASCADE", "", None),
    ("quarantine_fk_deferrable_initially_deferred",
     f"source_entity_id TEXT {_REF} DEFERRABLE INITIALLY DEFERRED", "", None),
    ("quarantine_fk_deferrable_initially_immediate",
     f"source_entity_id TEXT {_REF} DEFERRABLE INITIALLY IMMEDIATE", "", None),
    ("quarantine_column_integer_default", f"source_entity_id INTEGER DEFAULT 7 {_REF}", "", None),
    ("quarantine_composite_fk", "source_entity_id TEXT",
     ", FOREIGN KEY(source_entity_id, source_id) "
     "REFERENCES source_index_entities(source_entity_id, created_at)", None),
    ("quarantine_two_separate_fks", f"source_entity_id TEXT {_REF}",
     f", FOREIGN KEY(source_entity_id) {_REF}", None),
    ("quarantine_correct_plus_duplicate_fk", f"source_entity_id TEXT {_REF}",
     f", FOREIGN KEY(source_entity_id) {_REF}", None),
    ("quarantine_table_level_fk_same_endpoint",
     "source_entity_id TEXT", f", FOREIGN KEY(source_entity_id) {_REF}", None),
    ("quarantine_extra_entity_index", f"source_entity_id TEXT {_REF}", "",
     ("CREATE INDEX idx_q_extra_entity ON source_index_scan_quarantine(source_entity_id)",)),
    ("quarantine_expression_entity_index", f"source_entity_id TEXT {_REF}", "",
     ("CREATE INDEX idx_q_expr_entity ON source_index_scan_quarantine((source_entity_id || ''))",)),
]


@pytest.mark.parametrize(
    "case_id, entity_col, table_constraints, extra_indexes",
    _FAIL_QUARANTINE, ids=[c[0] for c in _FAIL_QUARANTINE],
)
def test_r8_quarantine_drift_fails_closed(
    fresh, case_id, entity_col, table_constraints, extra_indexes
) -> None:
    _recreate_quarantine(
        fresh, entity_col=entity_col, table_constraints=table_constraints,
        extra_indexes=extra_indexes or (),
    )
    _insert_quarantine_keep_row(fresh)
    assert _current(fresh) is False
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()
    assert _current(fresh) is False
    assert _keep_entity_id(
        fresh, "source_index_scan_quarantine", "quarantine_id", "keep-q"
    ) != "__row_absent__"


# --- Unrelated non-source_entity_id index is NOT policed (R8-AC-002C) -------------------------------


def test_r8_unrelated_index_ignored_events(fresh) -> None:
    with sqlite3.connect(fresh) as c:
        c.execute(
            "CREATE INDEX idx_ev_unrelated ON source_intelligence_events(created_at)"
        )
    assert _current(fresh) is True  # extra index on a non-entity column does not fail parity


def test_r8_unrelated_index_ignored_quarantine(fresh) -> None:
    with sqlite3.connect(fresh) as c:
        c.execute(
            "CREATE INDEX idx_q_unrelated ON source_index_scan_quarantine(status)"
        )
    assert _current(fresh) is True


# --- FK-clause parser fails closed on an unparseable/ambiguous entity FK (R8-AC-002E) ---------------


def test_r8_fk_parser_rejects_ambiguous_duplicate_entity_fk() -> None:
    sql = (
        "CREATE TABLE t (source_entity_id TEXT REFERENCES x(source_entity_id), "
        "FOREIGN KEY(source_entity_id) REFERENCES x(source_entity_id))"
    )
    with pytest.raises(V128OracleError):
        migrator_module._v128_parse_fk_clause_signature(sql)


def test_r8_fk_parser_extracts_deferrability_and_kind() -> None:
    sig = migrator_module._v128_parse_fk_clause_signature(
        "CREATE TABLE t (source_entity_id TEXT REFERENCES x(source_entity_id) "
        "ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED)"
    )
    assert sig.declaration_kind == "column"
    assert sig.source_columns == ("source_entity_id",)
    assert sig.on_delete == "CASCADE"
    assert sig.deferrability == "deferrable"
    assert sig.initially == "deferred"


# --- Atomic, deeply-immutable reference bundle (R8-AC-001 / 001A / 001B) ----------------------------


def test_r8_reference_published_is_immutable() -> None:
    migrator_module._V128_REFERENCE = None
    ref = SQLiteMigrator._v128_canonical_schema()
    assert ref is not None
    with pytest.raises(TypeError):  # MappingProxyType is read-only
        ref.owned_schema["injected"] = "x"  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.owned_schema = {}  # type: ignore[misc]
    contract = next(iter(ref.nonfk_contracts.values()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.column = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        ref.nonfk_contracts["injected"] = contract  # type: ignore[index]


def test_r8_atomic_build_failure_leaves_cache_unset_then_rebuilds() -> None:
    migrator_module._V128_REFERENCE = None
    orig = migrator_module._v128_extract_nonfk_contract

    def boom(conn, table):  # noqa: ANN001, ANN202
        raise RuntimeError("injected_midbuild_failure")

    migrator_module._v128_extract_nonfk_contract = boom
    try:
        with pytest.raises(RuntimeError, match="injected_midbuild_failure"):
            SQLiteMigrator._v128_canonical_schema()
        # published cache stays unset on failure.
        assert migrator_module._V128_REFERENCE is None
    finally:
        migrator_module._v128_extract_nonfk_contract = orig
    # the next call rebuilds cleanly.
    ref = SQLiteMigrator._v128_canonical_schema()
    assert ref is not None and dict(ref.owned_schema)


def test_r8_failure_cleanup_removes_builder_identity_and_releases_lock() -> None:
    migrator_module._V128_REFERENCE = None
    orig = migrator_module._v128_extract_nonfk_contract

    def boom(conn, table):  # noqa: ANN001, ANN202
        raise RuntimeError("injected_cleanup_probe")

    migrator_module._v128_extract_nonfk_contract = boom
    try:
        with pytest.raises(RuntimeError, match="injected_cleanup_probe"):
            SQLiteMigrator._v128_canonical_schema()
        assert migrator_module._V128_REFERENCE is None
        # thread-local builder identity removed via ``del`` (not a lingering closed connection).
        assert not hasattr(migrator_module._V128_BUILD_STATE, "conn")
        # the single-flight lock was released.
        assert not migrator_module._V128_BUILD_LOCK.locked()
    finally:
        migrator_module._v128_extract_nonfk_contract = orig
    assert SQLiteMigrator._v128_canonical_schema() is not None


# --- Connection-bound, single-flight, reentrancy-safe bootstrap (R8-AC-003 / 004) ------------------


def test_r8_two_thread_single_flight_blocks_non_builder(fresh, monkeypatch) -> None:
    # A malformed DB (owned-table drift) for the validating (non-builder) thread.
    mal = str(Path(fresh).with_name("mal.sqlite"))
    shutil.copy(fresh, mal)
    with sqlite3.connect(mal) as c:
        c.execute("DROP TABLE source_index_move_signals")

    migrator_module._V128_REFERENCE = None
    bootstrap_threads: list[int] = []
    orig_boot = SQLiteMigrator._v128_schema_structural_ok

    def rec_boot(conn):  # noqa: ANN001, ANN202
        bootstrap_threads.append(threading.get_ident())
        return orig_boot(conn)

    monkeypatch.setattr(SQLiteMigrator, "_v128_schema_structural_ok", staticmethod(rec_boot))

    builder_parked = threading.Event()
    release = threading.Event()

    def barrier() -> None:
        builder_parked.set()
        assert release.wait(10)

    migrator_module._V128_BUILD_BARRIER = barrier

    result: dict[str, object] = {}

    def builder() -> None:
        result["ref"] = SQLiteMigrator._v128_canonical_schema()

    def validator() -> None:
        c = get_connection(mal)
        try:
            result["val"] = SQLiteMigrator._v128_schema_current(c)
        finally:
            c.close()

    bt = threading.Thread(target=builder)
    bt.start()
    assert builder_parked.wait(10)  # builder holds the lock + thread-local, parked in the barrier
    vt = threading.Thread(target=validator)
    vt.start()
    vt.join(1.0)
    try:
        assert vt.is_alive()  # the non-builder caller BLOCKS on the single-flight lock (no bootstrap)
    finally:
        release.set()
        bt.join(10)
        vt.join(10)
    assert result["ref"] is not None
    assert result["val"] is False  # once published, the malformed DB is rejected
    assert set(bootstrap_threads) == {bt.ident}  # ONLY the builder invoked the bootstrap


def test_r8_same_thread_reentrancy_fails_closed_without_second_build(fresh) -> None:
    migrator_module._V128_REFERENCE = None
    other = get_connection(fresh)  # a DIFFERENT connection than the builder's scratch conn
    seen: list[str] = []

    def barrier() -> None:
        # Runs synchronously ON the builder thread, mid-build, with the thread-local conn set.
        try:
            SQLiteMigrator._v128_schema_current(other)
            seen.append("no_raise")
        except V128OracleError as exc:
            seen.append(str(exc))

    migrator_module._V128_BUILD_BARRIER = barrier
    try:
        ref = SQLiteMigrator._v128_canonical_schema()
    finally:
        migrator_module._V128_BUILD_BARRIER = None
        other.close()

    # (5) dedicated reentrancy error; (6) barrier ran exactly once -> NO second scratch construction;
    # (8) exactly one reference published; the original authorized build completed.
    assert seen == ["v128_reference_build_reentrancy"]
    assert ref is not None
    assert migrator_module._V128_REFERENCE is ref


# ===================================================================================================
# CP-PI-WI-02-R9 (R7-ORACLE-GAP-001): complete entity-index detection — auto-indexes included, a
# structured fail-closed key-expression parser, and a type-homogeneous ordered signature. Additive
# to the R8 suite; touches only the entity-index detection path.
# ===================================================================================================


# --- R9-AC-001B / 002 / 003: direct unit suite for the key-expression parser (symmetric controls) ---

# True: a genuine source_entity_id COLUMN reference (bare / mixed-case / each quoted form / inside a
# function / CAST-value / COLLATE-operand / a real column ref alongside a string literal).
_EXPR_TRUE = [
    "source_entity_id",
    "SOURCE_ENTITY_ID",
    '"source_entity_id"',
    "`source_entity_id`",
    "[source_entity_id]",
    "lower(source_entity_id)",
    "CAST(source_entity_id AS TEXT)",
    "source_entity_id COLLATE NOCASE",
    'coalesce(CAST("source_entity_id" AS TEXT), \'\')',
    "coalesce(source_entity_id, 'source_entity_id')",
]

# False: not a column reference — string literal (plain + ''-escaped), line/block comment, and the
# per-token function-name / type-name / collation-name roles, plus no-mention controls.
_EXPR_FALSE = [
    "'source_entity_id'",
    "'don''t reference source_entity_id'",
    "-- source_entity_id",
    "/* source_entity_id */",
    "source_entity_id(status)",
    "CAST(status AS source_entity_id)",
    "status COLLATE source_entity_id",
    "lower(status)",
    "CAST(status AS TEXT)",
    "status COLLATE NOCASE",
]

# Malformed/unterminated -> V128OracleError (ambiguity fails closed, never a silent False).
_EXPR_RAISES = [
    "'unterminated string",
    "/* unterminated comment",
    '"unterminated quoted ident',
]


@pytest.mark.parametrize("expr", _EXPR_TRUE)
def test_r9_expr_references_column_true(expr) -> None:
    assert migrator_module._v128_expr_references_column(expr, "source_entity_id") is True


@pytest.mark.parametrize("expr", _EXPR_FALSE)
def test_r9_expr_references_column_false(expr) -> None:
    assert migrator_module._v128_expr_references_column(expr, "source_entity_id") is False


@pytest.mark.parametrize("expr", _EXPR_RAISES)
def test_r9_expr_references_column_raises(expr) -> None:
    with pytest.raises(V128OracleError):
        migrator_module._v128_expr_references_column(expr, "source_entity_id")


# --- R9-AC-001: focused signature unit test on a PINNED probe table (pk + u autoindexes, sql NULL) ---


def test_r9_entity_index_signatures_probe_autoindexes(tmp_path) -> None:
    """A composite PK + a table-level UNIQUE on an ordinary rowid table yields SQL-less origin='pk' and
    origin='u' autoindexes; assert SQLite reports that form FIRST (guard against build-dependent table
    shapes), THEN the helper's ordered, name-independent ("auto", ...) descriptors — isolating the
    origin='pk' descriptor a whole-table test could otherwise pass via the column ``pk`` facet alone."""
    db = str(tmp_path / "probe.sqlite")
    with sqlite3.connect(db) as c:
        c.execute(
            "CREATE TABLE probe ("
            "  source_entity_id TEXT, status TEXT, other TEXT,"
            "  PRIMARY KEY (source_entity_id, status),"
            "  UNIQUE (source_entity_id, other)"
            ")"
        )
    with sqlite3.connect(db) as c:
        index_list = c.execute("PRAGMA index_list(probe)").fetchall()
        origins = {row[3] for row in index_list}
        assert origins == {"pk", "u"}  # exactly one pk autoindex, one u autoindex
        assert len(index_list) == 2
        for row in index_list:
            stored = c.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (row[1],)
            ).fetchone()
            assert stored[0] is None  # both are auto-created, sqlite_master.sql IS NULL
        sigs = migrator_module._v128_entity_index_signatures(c, "probe")
    assert sigs == (
        ("auto", "pk", 1, 0, ((0, "source_entity_id", 0, "BINARY"), (1, "status", 0, "BINARY"))),
        ("auto", "u", 1, 0, ((0, "source_entity_id", 0, "BINARY"), (2, "other", 0, "BINARY"))),
    )


def test_r9_entity_index_signatures_named_column_case_insensitive(tmp_path) -> None:
    """R9-AC-001A: a plain ``ON t(SOURCE_ENTITY_ID)`` is exposed by index_xinfo as the NAMED column
    (cid>=0) and detected by case-insensitive comparison — NOT via the expression parser. The table
    column is declared upper-case so index_xinfo returns 'SOURCE_ENTITY_ID', exercising the .lower()."""
    db = str(tmp_path / "named.sqlite")
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE t ("SOURCE_ENTITY_ID" TEXT, status TEXT)')
        c.execute("CREATE INDEX ix ON t(source_entity_id)")
        xinfo = c.execute("PRAGMA index_xinfo(ix)").fetchall()
        # the key term is a named column (cid>=0), NOT an expression (cid==-2).
        assert [xr[1] for xr in xinfo if int(xr[5]) == 1] == [0]
        sigs = migrator_module._v128_entity_index_signatures(c, "t")
    assert len(sigs) == 1
    assert sigs[0][0] == "sql"


# --- R9-AC-001A / 002 / 003 / 004 / 005: integration drift, per non-FK table, via GENUINE key exprs --

_NONFK = [
    ("source_intelligence_events", _recreate_events, _insert_events_keep_row, "event_id", "keep-ev"),
    (
        "source_index_scan_quarantine",
        _recreate_quarantine,
        _insert_quarantine_keep_row,
        "quarantine_id",
        "keep-q",
    ),
]

# Fail-closed drift cases: an entity-involving KEY (auto UNIQUE/composite, or a genuine cid==-2 key
# expression in any case / quoted form) added ON TOP of the canonical named index -> parity False,
# apply() raises + rollback preserves schema + data. Each entry is (case_id, table_constraints,
# extra_index_template) where "{t}" is the table name.
_R9_FAIL = [
    ("auto_unique_entity", ", UNIQUE(source_entity_id)", None),
    ("auto_unique_composite", ", UNIQUE(source_entity_id, status)", None),
    ("expr_case_varied", "", "CREATE INDEX idx_r9_x ON {t}((SOURCE_ENTITY_ID || ''))"),
    ("expr_quoted_double", "", 'CREATE INDEX idx_r9_x ON {t}(lower("source_entity_id"))'),
    ("expr_quoted_backtick", "", "CREATE INDEX idx_r9_x ON {t}(coalesce(`source_entity_id`, ''))"),
    ("expr_quoted_bracket", "", "CREATE INDEX idx_r9_x ON {t}(trim([source_entity_id]))"),
]


@pytest.mark.parametrize("case_id, table_constraints, extra_tmpl", _R9_FAIL, ids=[c[0] for c in _R9_FAIL])
@pytest.mark.parametrize(
    "table, recreate, insert_keep, pk_col, pk_val", _NONFK, ids=[c[0] for c in _NONFK]
)
def test_r9_entity_key_drift_fails_closed(
    fresh, table, recreate, insert_keep, pk_col, pk_val, case_id, table_constraints, extra_tmpl
) -> None:
    extra = (extra_tmpl.format(t=table),) if extra_tmpl else ()
    recreate(
        fresh, entity_col=f"source_entity_id TEXT {_REF}",
        table_constraints=table_constraints, extra_indexes=extra,
    )
    insert_keep(fresh)
    assert _current(fresh) is False  # the entity-involving key is detected
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()
    # rollback preserved the drift (schema) and the seeded row (data).
    assert _current(fresh) is False
    assert _keep_entity_id(fresh, table, pk_col, pk_val) != "__row_absent__"
    if extra_tmpl:
        assert "idx_r9_x" in _indexes(fresh, table)


# True (no false rejection): an entity-mention that is NOT a key column reference — a string literal, a
# line/block comment, a CAST type name, or a predicate-only index (key unrelated) -> parity stays True.
_R9_TRUE = [
    ("string_literal_key", "CREATE INDEX idx_r9_t ON {t}((status || 'source_entity_id'))"),
    ("line_comment_key", "CREATE INDEX idx_r9_t ON {t}((status || '' -- source_entity_id\n))"),
    ("block_comment_key", "CREATE INDEX idx_r9_t ON {t}((status /* source_entity_id */ || ''))"),
    ("cast_type_name_key", "CREATE INDEX idx_r9_t ON {t}(CAST(status AS source_entity_id))"),
    ("predicate_only", "CREATE INDEX idx_r9_t ON {t}(status) WHERE source_entity_id IS NOT NULL"),
]


@pytest.mark.parametrize("case_id, stmt_tmpl", _R9_TRUE, ids=[c[0] for c in _R9_TRUE])
@pytest.mark.parametrize(
    "table, recreate, insert_keep, pk_col, pk_val", _NONFK, ids=[c[0] for c in _NONFK]
)
def test_r9_entity_mention_not_key_ref_stays_current(
    fresh, table, recreate, insert_keep, pk_col, pk_val, case_id, stmt_tmpl
) -> None:
    # The canonical named entity index stays intact on ``fresh``; add only the negative-control index.
    with sqlite3.connect(fresh) as c:
        c.execute(stmt_tmpl.format(t=table))
    assert _current(fresh) is True  # not a source_entity_id KEY reference -> not policed


# ===================================================================================================
# CP-PI-WI-02-R10 (R8-ORACLE-GAP-001/002): false-rejection-safe entity-index parsing — comment-aware
# key-region location, paren-balance fail-closed, and safe dynamic index-name binding. Additive to the
# R8/R9 suites; touches only the entity-index parsing path.
# ===================================================================================================


# --- R10-AC-001: direct unit suite for the shared whitespace/comment skip helper --------------------


def test_r10_skip_ws_comments_leading_whitespace() -> None:
    assert migrator_module._v128_skip_ws_comments("   x", 0) == 3


def test_r10_skip_ws_comments_line_comment() -> None:
    s = "-- ( comment\nx"
    assert migrator_module._v128_skip_ws_comments(s, 0) == s.index("x")


def test_r10_skip_ws_comments_line_comment_to_end() -> None:
    s = "-- ( no trailing newline"
    assert migrator_module._v128_skip_ws_comments(s, 0) == len(s)


def test_r10_skip_ws_comments_block_comment() -> None:
    s = "/* ( */x"
    assert migrator_module._v128_skip_ws_comments(s, 0) == s.index("x")


def test_r10_skip_ws_comments_mixed_run() -> None:
    s = "  -- a\n /* ( */  x"
    assert migrator_module._v128_skip_ws_comments(s, 0) == s.index("x")


def test_r10_skip_ws_comments_unterminated_block_raises() -> None:
    with pytest.raises(V128OracleError):
        migrator_module._v128_skip_ws_comments("/* unterminated", 0)


def test_r10_skip_ws_comments_no_skip_returns_same_index() -> None:
    # A non-ws, non-comment char (incl. a lone '-' or '/') is not skipped.
    assert migrator_module._v128_skip_ws_comments("(status", 0) == 0
    assert migrator_module._v128_skip_ws_comments("- x", 0) == 0
    assert migrator_module._v128_skip_ws_comments("/ x", 0) == 0


# --- R10-AC-002: paren-balance fail-closed (unbalanced input raises, never a silent verdict) ---------
# Asserted on _v128_expr_references_column (the entry that tokenizes the key-expression region; the
# tokenizer enforces balance). '(x))' is exercised here rather than on _v128_index_key_region because
# that extractor returns at the FIRST balanced close and never sees the trailing ')' — the balance
# contract lives in the key-expression parser.
@pytest.mark.parametrize("expr", ["((x)", "(x))", ")x)"])
def test_r10_expr_references_column_unbalanced_raises(expr) -> None:
    with pytest.raises(V128OracleError):
        migrator_module._v128_expr_references_column(expr, "source_entity_id")


def test_r10_nested_balanced_expr_still_detected() -> None:
    # Balance enforcement must not suppress a valid deeply-nested column reference.
    assert migrator_module._v128_expr_references_column(
        "(coalesce(lower(source_entity_id), ''))", "source_entity_id"
    ) is True


# --- R10-AC-001: comment-before-key-list, per non-FK table, at the exact defect positions -----------
# The '(' inside the comment sits exactly where the pre-R10 key-region scan would mistake it for the
# key list. Three placements: between the name and ON, between the table and the key list, and a '--'
# line comment before ON.
_R10_COMMENT_POS = [
    ("comment_between_name_and_on", "CREATE INDEX ix_r10 /* ( */ ON {t}(({expr}))"),
    ("comment_between_table_and_keylist", "CREATE INDEX ix_r10 ON {t} /* ( */ (({expr}))"),
    ("line_comment_before_on", "CREATE INDEX ix_r10 -- (\nON {t}(({expr}))"),
]
_R10_NONFK_TABLES = ["source_intelligence_events", "source_index_scan_quarantine"]


@pytest.mark.parametrize("pos_id, tmpl", _R10_COMMENT_POS, ids=[c[0] for c in _R10_COMMENT_POS])
@pytest.mark.parametrize("table", _R10_NONFK_TABLES)
def test_r10_comment_before_keylist_unrelated_stays_current(fresh, table, pos_id, tmpl) -> None:
    # An UNRELATED expression index (key `(status || '')`) whose preceding comment contains '(' must
    # not crash / false-reject the oracle: parity stays True and apply() is an idempotent no-op.
    with sqlite3.connect(fresh) as c:
        c.execute(tmpl.format(t=table, expr="status || ''"))
    assert _current(fresh) is True
    assert SQLiteMigrator(db_path=fresh).apply() == LATEST_SCHEMA_VERSION
    assert _current(fresh) is True
    assert "ix_r10" in _indexes(fresh, table)
    assert _fk_check(fresh) == []


@pytest.mark.parametrize("pos_id, tmpl", _R10_COMMENT_POS, ids=[c[0] for c in _R10_COMMENT_POS])
@pytest.mark.parametrize("table", _R10_NONFK_TABLES)
def test_r10_comment_before_keylist_entity_detected_fails_closed(fresh, table, pos_id, tmpl) -> None:
    # The SAME comment placement with a GENUINE entity key expression `(source_entity_id || '')` is
    # still detected (the comment does not defeat detection) -> parity False -> apply() fails closed.
    with sqlite3.connect(fresh) as c:
        c.execute(tmpl.format(t=table, expr="source_entity_id || ''"))
    assert _current(fresh) is False
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()
    assert _current(fresh) is False


# --- R10-AC-003: safe dynamic index-name binding (reserved word / whitespace-hyphen / embedded quote)


_R10_WEIRD_NAMES = [
    ('"select"', "reserved_word"),
    ('"weird - name"', "whitespace_hyphen"),
    ('"weird""quote"', "embedded_quote"),
]


@pytest.mark.parametrize("iname, name_id", _R10_WEIRD_NAMES, ids=[c[1] for c in _R10_WEIRD_NAMES])
def test_r10_entity_index_signatures_weird_named_unrelated(tmp_path, iname, name_id) -> None:
    # Production path: a weird-named UNRELATED index must not raise sqlite3.OperationalError (the
    # pre-R10 unquoted PRAGMA interpolation did) and yields no entity signature.
    db = str(tmp_path / "probe.sqlite")
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE t (source_entity_id TEXT, status TEXT)")
        c.execute(f"CREATE INDEX {iname} ON t(status)")
        assert migrator_module._v128_entity_index_signatures(c, "t") == ()


@pytest.mark.parametrize("iname, name_id", _R10_WEIRD_NAMES, ids=[c[1] for c in _R10_WEIRD_NAMES])
def test_r10_entity_index_signatures_weird_named_entity_detected(tmp_path, iname, name_id) -> None:
    # Production path: a weird-named ENTITY-bearing index is still detected (one signature), bound-name
    # safe.
    db = str(tmp_path / "probe.sqlite")
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE t (source_entity_id TEXT, status TEXT)")
        c.execute(f"CREATE INDEX {iname} ON t(source_entity_id)")
        sigs = migrator_module._v128_entity_index_signatures(c, "t")
    assert len(sigs) == 1
    assert sigs[0][0] == "sql"


@pytest.mark.parametrize("iname, name_id", _R10_WEIRD_NAMES, ids=[c[1] for c in _R10_WEIRD_NAMES])
@pytest.mark.parametrize("table", _R10_NONFK_TABLES)
def test_r10_weird_named_unrelated_index_stays_current(fresh, table, iname, name_id) -> None:
    # Through _v128_schema_current: a weird-named UNRELATED index on a non-FK table keeps parity True
    # (no OperationalError from the introspection pragmas).
    with sqlite3.connect(fresh) as c:
        c.execute(f"CREATE INDEX {iname} ON {table}(status)")
    assert _current(fresh) is True


@pytest.mark.parametrize("iname, name_id", _R10_WEIRD_NAMES, ids=[c[1] for c in _R10_WEIRD_NAMES])
@pytest.mark.parametrize("table", _R10_NONFK_TABLES)
def test_r10_weird_named_entity_index_detected_fails_closed(fresh, table, iname, name_id) -> None:
    # Through _v128_schema_current: a weird-named ENTITY index is detected (parity False, no
    # OperationalError leak) -> apply() fails closed.
    with sqlite3.connect(fresh) as c:
        c.execute(f"CREATE INDEX {iname} ON {table}(source_entity_id)")
    assert _current(fresh) is False
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        SQLiteMigrator(db_path=fresh).apply()
    assert _current(fresh) is False
