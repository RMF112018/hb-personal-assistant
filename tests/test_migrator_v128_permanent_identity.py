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
