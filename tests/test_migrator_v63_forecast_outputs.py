"""Phase 2a — V63 additive migration tests (forecast run-output tables).

Covers: migration applies to V63 and is idempotent (prior versions preserved); all ten
run-output tables present and empty; the lifecycle contract table_count and classification
track the schema (412 -> 422). Additive schema only — no network, no Ollama, no CFR.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.forecast_output_tables import V63_TABLES
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _migrated_db(td: str) -> str:
    db = Path(td) / "v63.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_latest_schema_version_is_at_least_63() -> None:
    assert LATEST_SCHEMA_VERSION >= 63


def test_migration_applies_v63_with_all_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert [t for t in V63_TABLES if t not in names] == []
        assert len(V63_TABLES) == 10


def test_migration_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v63.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        n63 = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=63").fetchone()[0]
        assert n63 == 1
        # Prior forecast versions still recorded.
        for v in (58, 59, 60, 61, 62, 63):
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version=?", (v,)
                ).fetchone()[0]
                == 1
            )
        conn.close()


def test_v63_tables_ship_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        for t in V63_TABLES:
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        conn.close()


def test_forecast_outputs_declares_run_fk() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        fks = conn.execute("PRAGMA foreign_key_list(forecast_outputs)").fetchall()
        conn.close()
        # one FK: run_id -> forecast_runs(run_id)
        assert any(row[2] == "forecast_runs" and row[3] == "run_id" for row in fks)


def test_lifecycle_contract_count_and_v63_classification() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == 464
    assert contract["table_count"] == len(contract["tables"])
    for t in V63_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "forecast_output_v63"
        assert entry["lifecycle_status"] == "operational_empty_expected"
        assert entry["v"] == "V63"
