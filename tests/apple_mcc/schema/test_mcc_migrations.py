"""MCC migration tip tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION


def test_latest_is_135() -> None:
    assert LATEST_SCHEMA_VERSION == 135


def test_mcc_tables_exist(disposable_db: Path) -> None:
    conn = sqlite3.connect(str(disposable_db))
    try:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for t in (
            "email_message_source_observations",
            "email_message_revisions",
            "email_message_current_selection",
            "calendar_event_source_observations",
            "calendar_event_revisions",
            "calendar_event_current_selection",
        ):
            assert t in tables, t
        ver = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        assert int(ver) == 135
        for table in (
            "email_message_source_observations",
            "calendar_event_source_observations",
            "contact_source_observations",
            "contact_entities",
        ):
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            assert "source_account" in cols, table
            if table != "contact_entities":
                assert "source_scope" in cols, table
    finally:
        conn.close()


import pytest
from pathlib import Path
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

@pytest.fixture
def disposable_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HB_DB_STORAGE_GUARD", "permissive")
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    db = tmp_path / "rehearsal.sqlite"
    ver = SQLiteMigrator(db_path=str(db)).apply()
    assert int(ver) == LATEST_SCHEMA_VERSION
    return db

