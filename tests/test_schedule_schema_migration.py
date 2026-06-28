"""V62 schedule intelligence schema migration tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_tables import V62_TABLES

V62_COUNT = 13


def _migrated_db(td: str) -> str:
    db = Path(td) / "v62.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_latest_schema_version_is_at_least_62() -> None:
    assert LATEST_SCHEMA_VERSION >= 62


def test_v62_tables_present() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        missing = [t for t in V62_TABLES if t not in names]
        assert missing == []
        assert len(V62_TABLES) == V62_COUNT


def test_migration_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v62.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=62").fetchone()[0] == 1
        conn.close()


def test_v62_tables_empty_and_integrity() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        for t in V62_TABLES:
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        conn.close()


def test_lifecycle_contract_475() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == 475
    assert contract["table_count"] == len(contract["tables"])
    for t in V62_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "schedule_intelligence_v62"
        assert entry["v"] == "V62"
