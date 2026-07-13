"""Phase B / B4 corrective — V127 events-table rebuild ('moved' type + dest_rel_path + next_attempt_at).

Proves the rebuild widens the event_type CHECK to accept 'moved', adds the two nullable columns, PRESERVES
every existing queued row + event_id, keeps both indexes, is idempotent, and — critically — parity is
validated on more than column presence: a table that has the new columns but retains the OLD CHECK (or is
otherwise incomplete) is REBUILT, never falsely marked applied. Uses scratch SQLite DBs only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.source_intelligence_tables import EVENT_TYPE_VALUES

# Old (pre-V127) events DDL — historical shape, no dest_rel_path/next_attempt_at, CHECK WITHOUT 'moved'.
_OLD_CHECK = ", ".join(f"'{v}'" for v in EVENT_TYPE_VALUES)
_OLD_EVENTS_DDL = (
    "CREATE TABLE source_intelligence_events ("
    " event_id TEXT PRIMARY KEY, source_id TEXT, rel_path TEXT, source_root_key TEXT,"
    f" event_type TEXT NOT NULL CHECK(event_type IN ({_OLD_CHECK})),"
    " status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN"
    " ('queued','processing','done','error','skipped')),"
    " error_code TEXT, attempts INTEGER NOT NULL DEFAULT 0,"
    " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
    " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
)


def _cols(db: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute("PRAGMA table_info(source_intelligence_events)").fetchall()}


def _indexes(db: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute("PRAGMA index_list(source_intelligence_events)").fetchall()}


def _versions(db: str) -> set[int]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT version FROM schema_migrations").fetchall()}


def _revert_to_old_events(db: str, *, with_new_columns: bool, rows: list[tuple[str, str]]) -> None:
    """Simulate a pre-V127 (or torn) events table and un-record V127 so the next apply() re-runs it.

    ``with_new_columns`` False → genuine pre-V127 shape. True → the columns exist but the CHECK is still
    the OLD one (the exact 'columns present but stale CHECK' case parity must catch). ``rows`` are
    (event_id, event_type) queued rows to seed for preservation checks."""
    ddl = _OLD_EVENTS_DDL
    if with_new_columns:
        ddl = ddl[:-1] + ", dest_rel_path TEXT, next_attempt_at TEXT)"
    with sqlite3.connect(db) as c:
        c.execute("DROP TABLE source_intelligence_events")
        c.execute(ddl)
        c.execute("CREATE INDEX idx_si_events_status ON source_intelligence_events(status, created_at)")
        c.execute("CREATE INDEX idx_si_events_source ON source_intelligence_events(source_id)")
        for eid, et in rows:
            c.execute("INSERT INTO source_intelligence_events(event_id, event_type, status) "
                      "VALUES(?,?,'queued')", (eid, et))
        c.execute("DELETE FROM schema_migrations WHERE version = 127")
        c.commit()


@pytest.fixture()
def fresh(tmp_path: Path) -> str:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_latest_version_is_127(fresh) -> None:
    assert LATEST_SCHEMA_VERSION == 127
    assert 127 in _versions(fresh)


def test_columns_and_indexes_present(fresh) -> None:
    assert {"dest_rel_path", "next_attempt_at"}.issubset(_cols(fresh))
    assert {"idx_si_events_status", "idx_si_events_source"}.issubset(_indexes(fresh))


def test_moved_and_legacy_types_accepted(fresh) -> None:
    repo = SourceIndexRepository(fresh)
    # public enqueue path (not a raw INSERT) — proves the runtime authority + CHECK accept 'moved'
    repo.enqueue_event(event_type="moved", rel_path="a", dest_rel_path="b", source_root_key="R")
    repo.enqueue_event(event_type="created", rel_path="c", source_root_key="R")
    repo.enqueue_event(event_type="deleted", rel_path="d", source_root_key="R")
    with sqlite3.connect(fresh) as c:
        kinds = {r[0] for r in c.execute("SELECT event_type FROM source_intelligence_events").fetchall()}
    assert {"moved", "created", "deleted"}.issubset(kinds)


def test_rebuild_from_old_shape_preserves_rows_and_ids(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _revert_to_old_events(db, with_new_columns=False,
                          rows=[("evt-1", "created"), ("evt-2", "deleted")])
    assert "dest_rel_path" not in _cols(db)  # confirm we are genuinely pre-V127
    # re-apply -> V127 rebuild fires
    assert SQLiteMigrator(db_path=db).apply() == 127
    assert {"dest_rel_path", "next_attempt_at"}.issubset(_cols(db))
    with sqlite3.connect(db) as c:
        preserved = {r[0]: r[1] for r in c.execute(
            "SELECT event_id, event_type FROM source_intelligence_events").fetchall()}
    assert preserved == {"evt-1": "created", "evt-2": "deleted"}  # rows + IDs preserved
    # 'moved' now accepted after the rebuild
    SourceIndexRepository(db).enqueue_event(event_type="moved", rel_path="x", dest_rel_path="y",
                                            source_root_key="R")


def test_parity_incomplete_table_is_rebuilt_not_marked_applied(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # columns present BUT the OLD CHECK (rejects 'moved') + V127 un-recorded — a torn/partial state.
    _revert_to_old_events(db, with_new_columns=True, rows=[("evt-1", "created")])
    assert {"dest_rel_path", "next_attempt_at"}.issubset(_cols(db))  # columns alone are NOT enough
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        # old CHECK really rejects 'moved' pre-repair
        c.execute("INSERT INTO source_intelligence_events(event_id,event_type,status) "
                  "VALUES('probe','moved','queued')")
    # re-apply -> parity probe fails on the stale CHECK -> full rebuild -> now accepts 'moved'
    assert SQLiteMigrator(db_path=db).apply() == 127
    assert 127 in _versions(db)
    SourceIndexRepository(db).enqueue_event(event_type="moved", rel_path="x", dest_rel_path="y",
                                            source_root_key="R")
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT event_type FROM source_intelligence_events "
                         "WHERE event_id='evt-1'").fetchone()[0] == "created"  # legacy row survived


def test_idempotent_reapply(fresh) -> None:
    for _ in range(3):
        assert SQLiteMigrator(db_path=fresh).apply() == 127


def test_v122_to_v126_preserved(fresh) -> None:
    assert {122, 123, 124, 125, 126, 127}.issubset(_versions(fresh))


# ---------------- PB-011 / PLAN-C2R2-003: exact structural parity + adaptive lossless repair ----------------

def _get_conn(db: str):
    from hb_assistant.store.migrator import get_connection
    return get_connection(db)


def test_fresh_table_is_schema_current_no_false_rebuild(fresh) -> None:
    # A freshly-migrated table MUST pass exact parity, else it would rebuild on every apply().
    c = _get_conn(fresh)
    try:
        assert SQLiteMigrator._events_schema_current(c) is True
    finally:
        c.close()


def _install_events(db: str, ddl: str, rows: list[tuple[str, str]], *, keep_v127: bool,
                    indexes: list[str] | None = None) -> None:
    idx = indexes if indexes is not None else [
        "CREATE INDEX idx_si_events_status ON source_intelligence_events(status, created_at)",
        "CREATE INDEX idx_si_events_source ON source_intelligence_events(source_id)",
    ]
    with sqlite3.connect(db) as c:
        c.execute("DROP TABLE source_intelligence_events")
        c.execute(ddl)
        for stmt in idx:
            c.execute(stmt)
        for eid, et in rows:
            c.execute("INSERT INTO source_intelligence_events(event_id,event_type,status) "
                      "VALUES(?,?,'queued')", (eid, et))
        if not keep_v127:
            c.execute("DELETE FROM schema_migrations WHERE version=127")
        c.commit()


def test_missing_attempts_column_rebuilds_losslessly_even_with_v127_recorded(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # malformed: NO 'attempts' column, but version 127 stays recorded (always-revalidate must still repair)
    _install_events(
        db,
        "CREATE TABLE source_intelligence_events (event_id TEXT PRIMARY KEY, source_id TEXT, "
        "rel_path TEXT, source_root_key TEXT, event_type TEXT, status TEXT, error_code TEXT, "
        "dest_rel_path TEXT, next_attempt_at TEXT, created_at TEXT, updated_at TEXT)",
        [("e1", "created")], keep_v127=True,
    )
    assert SQLiteMigrator(db_path=db).apply() == 127
    assert "attempts" in _cols(db)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT event_type, attempts FROM source_intelligence_events "
                         "WHERE event_id='e1'").fetchone() == ("created", 0)  # lossless; attempts→0


def test_wrong_status_default_rebuilds(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # columns present + moved accepted, but 'status' is nullable with the WRONG default → parity False.
    _install_events(
        db,
        "CREATE TABLE source_intelligence_events (event_id TEXT PRIMARY KEY, source_id TEXT, "
        "rel_path TEXT, source_root_key TEXT, dest_rel_path TEXT, next_attempt_at TEXT, "
        "event_type TEXT NOT NULL CHECK(event_type IN "
        "('created','modified','deleted','reindex_requested','rebuild','moved')), "
        "status TEXT DEFAULT 'wrong', error_code TEXT, attempts INTEGER NOT NULL DEFAULT 0, "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        [("e1", "created")], keep_v127=False,
    )
    c = _get_conn(db)
    try:
        assert SQLiteMigrator._events_schema_current(c) is False  # wrong default/nullability detected
    finally:
        c.close()
    assert SQLiteMigrator(db_path=db).apply() == 127
    c = _get_conn(db)
    try:
        assert SQLiteMigrator._events_schema_current(c) is True
    finally:
        c.close()


def test_index_right_name_wrong_columns_rebuilds(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # correct column set + moved accepted, but idx_si_events_source indexes the WRONG column.
    _install_events(
        db,
        "CREATE TABLE source_intelligence_events (event_id TEXT PRIMARY KEY, source_id TEXT, "
        "rel_path TEXT, source_root_key TEXT, dest_rel_path TEXT, next_attempt_at TEXT, "
        "event_type TEXT NOT NULL CHECK(event_type IN "
        "('created','modified','deleted','reindex_requested','rebuild','moved')), "
        "status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN "
        "('queued','processing','done','error','skipped')), "
        "error_code TEXT, attempts INTEGER NOT NULL DEFAULT 0, "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        [("e1", "created")], keep_v127=False,
        indexes=[
            "CREATE INDEX idx_si_events_status ON source_intelligence_events(status, created_at)",
            "CREATE INDEX idx_si_events_source ON source_intelligence_events(event_id)",  # wrong column
        ],
    )
    c = _get_conn(db)
    try:
        assert SQLiteMigrator._events_schema_current(c) is False  # wrong index columns detected
    finally:
        c.close()
    assert SQLiteMigrator(db_path=db).apply() == 127
    cols = [r[2] for r in sqlite3.connect(db).execute(
        "PRAGMA index_info(idx_si_events_source)").fetchall()]
    assert cols == ["source_id"]  # index repaired


def test_invalid_existing_rows_fail_closed_and_roll_back(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _install_events(
        db,
        "CREATE TABLE source_intelligence_events (event_id TEXT PRIMARY KEY, source_id TEXT, "
        "rel_path TEXT, source_root_key TEXT, event_type TEXT, status TEXT, error_code TEXT, "
        "attempts INTEGER, created_at TEXT, updated_at TEXT)",
        [("keep", "created"), ("bad", "__nope__")], keep_v127=False,  # bad event_type
    )
    with pytest.raises(RuntimeError, match="v127_events_invalid_existing_rows"):
        SQLiteMigrator(db_path=db).apply()
    # whole migration rolled back: malformed table + invalid row retained, v127 not recorded
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT event_type FROM source_intelligence_events "
                         "WHERE event_id='bad'").fetchone()[0] == "__nope__"
    assert 127 not in _versions(db)
