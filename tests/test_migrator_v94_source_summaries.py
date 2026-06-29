"""V94 source-summary receipt migration: additive, advisory CHECK, idempotent."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def test_latest_schema_version_is_at_least_94() -> None:
    assert LATEST_SCHEMA_VERSION >= 94


def test_summaries_table_created_additive(tmp_path: Path) -> None:
    db = str(tmp_path / "v94.sqlite")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "source_intelligence_summaries" in names
    # prior source-intelligence tables still present (additive)
    for prior in ("source_intelligence_sources", "source_intelligence_generated_notes", "email_messages"):
        assert prior in names, prior
    sql = con.execute(
        "SELECT sql FROM sqlite_master WHERE name='source_intelligence_summaries'"
    ).fetchone()[0]
    assert "advisory = 1" in sql


def test_advisory_check_enforced(tmp_path: Path) -> None:
    db = str(tmp_path / "v94.sqlite")
    SQLiteMigrator(db_path=db).apply()
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO source_intelligence_sources(source_id, source_kind, rel_path) VALUES ('s1','external_file','a.md')"
    )
    con.execute(
        "INSERT INTO source_intelligence_summaries(source_id, model_provider, prompt_version) "
        "VALUES ('s1','ollama','v1')"
    )  # advisory defaults to 1 -> ok
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO source_intelligence_summaries(source_id, model_provider, prompt_version, advisory) "
            "VALUES ('s2','ollama','v1',0)"
        )


def test_reapply_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "v94.sqlite")
    SQLiteMigrator(db_path=db).apply()
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
