"""P6 — V72 additive migration tests (forecast model-registry tables).

Covers: migration applies to V72 and is idempotent (prior versions preserved); all three
model-registry tables present and empty; run/model FKs declared; lifecycle contract stays
self-consistent and the tables classify as the v72 model-registry family. Additive schema
only — no network, no CFR, no live DB.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.forecast_model_registry_tables import V72_TABLES
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _migrated_db(td: str) -> str:
    db = Path(td) / "v72.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_latest_schema_version_is_at_least_72() -> None:
    assert LATEST_SCHEMA_VERSION >= 72


def test_migration_applies_v72_with_all_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert [t for t in V72_TABLES if t not in names] == []
        assert len(V72_TABLES) == 3


def test_migration_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v72.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        n72 = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=72").fetchone()[0]
        assert n72 == 1
        for v in (58, 66, 71, 72):
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version=?", (v,)
                ).fetchone()[0]
                == 1
            )
        conn.close()


def test_v72_tables_ship_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        for t in V72_TABLES:
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        conn.close()


def test_run_model_versions_declares_fks() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        fks = conn.execute("PRAGMA foreign_key_list(forecast_run_model_versions)").fetchall()
        conn.close()
        targets = {(row[2], row[3], row[4]) for row in fks}  # (table, from?, to?) ordering varies
        tables = {row[2] for row in fks}
        assert "forecast_runs" in tables
        assert "forecast_model_versions" in tables
        assert targets  # non-empty


def test_calibration_weights_has_calibration_source_column() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(forecast_calibration_weights)")}
        conn.close()
        assert "calibration_source" in cols


def test_lifecycle_contract_self_consistent_and_v72_classification() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == len(contract["tables"])
    for t in V72_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "forecast_model_registry_v72"
        assert entry["lifecycle_status"] == "operational_empty_expected"
        assert entry["v"] == "V72"
