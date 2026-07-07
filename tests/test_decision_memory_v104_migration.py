"""V104 decision/preference/open-loop migration (N8C-8): additive, idempotent, prior rows survive."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_DM_TABLES = {
    "assistant_decision_records",
    "assistant_preference_records",
    "assistant_open_loop_records",
    "assistant_decision_memory_events",
}


def _tables(db: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_v104_present_and_head_at_least_104(tmp_path: Path) -> None:
    # V104 is additive; later migrations (V105+) advance the head without removing it.
    assert LATEST_SCHEMA_VERSION >= 104
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT name FROM schema_migrations WHERE version = 104").fetchone()
    assert row is not None and row[0] == "v104_assistant_decision_memory"


def test_apply_creates_four_decision_memory_tables(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    head = SQLiteMigrator(db_path=db).apply()
    assert head == LATEST_SCHEMA_VERSION
    assert _tables(db) >= _DM_TABLES


def test_migration_is_idempotent_applied_twice(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    first = SQLiteMigrator(db_path=db).apply()
    second = SQLiteMigrator(db_path=db).apply()
    assert first == second == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 104").fetchone()[0]
    assert rows == 1


def test_prior_v100_v101_v102_v103_rows_remain(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        for ver, name in ((100, "v100_assistant_claims"), (101, "v101_assistant_enrichment"),
                          (102, "v102_assistant_context_packs"), (103, "v103_assistant_memory")):
            row = c.execute("SELECT name FROM schema_migrations WHERE version = ?", (ver,)).fetchone()
            assert row is not None and row[0] == name
    names = _tables(db)
    assert {"assistant_claims", "assistant_enrichment_jobs", "assistant_context_packs",
            "assistant_memory_nodes"} <= names


def test_provenance_check_enforced(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        # A record with no provenance anchor violates the table CHECK.
        try:
            c.execute("INSERT INTO assistant_decision_records (decision_id, identity_key, decision_type) "
                      "VALUES ('d1', 'k1', 'decision')")
            raise AssertionError("provenance CHECK not enforced")
        except sqlite3.IntegrityError:
            pass
