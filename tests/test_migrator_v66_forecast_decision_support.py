"""Phase 2b — V66 additive migration tests (forecast decision-support tables).

Covers: migration applies to V66 and is idempotent (prior versions preserved); all eight
decision-support tables present and empty; lifecycle contract stays self-consistent and the
tables classify as the v66 decision-support family. Additive schema only — no network, no CFR.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.forecast_decision_support_tables import V66_TABLES
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _migrated_db(td: str) -> str:
    db = Path(td) / "v66.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_latest_schema_version_is_at_least_66() -> None:
    assert LATEST_SCHEMA_VERSION >= 66


def test_migration_applies_v66_with_all_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert [t for t in V66_TABLES if t not in names] == []
        assert len(V66_TABLES) == 8


def test_migration_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v66.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        n66 = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=66").fetchone()[0]
        assert n66 == 1
        for v in (58, 59, 60, 61, 62, 63, 64, 65, 66):
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version=?", (v,)
                ).fetchone()[0]
                == 1
            )
        conn.close()


def test_v66_tables_ship_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        for t in V66_TABLES:
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        conn.close()


def test_decision_support_declares_run_fks() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        fks = conn.execute(
            "PRAGMA foreign_key_list(forecast_project_maturity_snapshots)"
        ).fetchall()
        conn.close()
        assert any(row[2] == "forecast_runs" and row[3] == "run_id" for row in fks)


def test_lifecycle_contract_self_consistent_and_v66_classification() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == len(contract["tables"])
    for t in V66_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "forecast_decision_support_v66"
        assert entry["lifecycle_status"] == "operational_empty_expected"
        assert entry["v"] == "V66"
