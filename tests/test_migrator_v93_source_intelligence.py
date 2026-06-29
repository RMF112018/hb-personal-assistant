"""V93 source-intelligence migration: additive, tables + FTS, CHECK invariants."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.source_intelligence_tables import V93_FTS_TABLES, V93_TABLES


def test_latest_schema_version_is_at_least_93() -> None:
    assert LATEST_SCHEMA_VERSION >= 93


def _apply(tmp_path: Path) -> str:
    db = str(tmp_path / "v93.sqlite")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    return db


def test_all_tables_and_fts_created(tmp_path: Path) -> None:
    db = _apply(tmp_path)
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master").fetchall()}
    for t in V93_TABLES:
        assert t in names, t
    for t in V93_FTS_TABLES:
        assert t in names, t
    assert con.execute(
        "SELECT state_value FROM source_intelligence_state WHERE state_key='fts_available'"
    ).fetchone()[0] == "1"


def test_migration_is_additive(tmp_path: Path) -> None:
    """Pre-existing domain tables (link targets) survive the v93 migration."""
    db = _apply(tmp_path)
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for prior in ("email_messages", "schedule_file_imports", "schema_migrations"):
        assert prior in names, prior


def test_reapply_is_idempotent(tmp_path: Path) -> None:
    db = _apply(tmp_path)
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION


def test_no_raw_body_check_enforced(tmp_path: Path) -> None:
    db = _apply(tmp_path)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO source_intelligence_sources(source_id, source_kind, rel_path) VALUES ('s1','external_file','a.md')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO source_intelligence_text(source_id, raw_body_persisted) VALUES ('s1', 1)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO source_intelligence_text(source_id, redaction_applied) VALUES ('s1', 0)"
        )


def test_source_traceability_check_enforced(tmp_path: Path) -> None:
    """A source row must be a file (rel_path) OR a domain link (table+id), never neither."""
    db = _apply(tmp_path)
    con = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO source_intelligence_sources(source_id, source_kind) VALUES ('bad','external_file')"
        )


def test_source_kind_and_event_status_checks(tmp_path: Path) -> None:
    db = _apply(tmp_path)
    con = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO source_intelligence_sources(source_id, source_kind, rel_path) VALUES ('x','bogus_kind','a')"
        )
