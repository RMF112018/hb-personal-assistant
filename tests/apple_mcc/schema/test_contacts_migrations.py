"""Contacts migration tables tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def test_contact_tables(disposable_db: Path) -> None:
    conn = sqlite3.connect(str(disposable_db))
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in (
            "contact_entities",
            "apple_contact_raw_content",
            "contact_source_observations",
            "contact_revisions",
            "contact_current_selection",
            "contact_email_hashes",
            "contact_phone_hashes",
            "contact_linkage_candidates",
            "apple_contact_structured",
        ):
            assert t in tables, t
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

