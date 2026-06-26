"""Phase 4 — V61 additive migration tests (external-forecast evaluation tables).

Covers: migration applies to V61 and is idempotent (prior versions preserved); all eight
external-forecast tables present and empty; the forecast_origin discriminator default;
the lifecycle contract table_count and classification track the schema (391 -> 399). Additive
schema only — no network, no Ollama, no CFR.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

V61_TABLES = [
    "forecast_external_forecasts",
    "forecast_external_forecast_rows",
    "forecast_external_forecast_mappings",
    "forecast_accuracy_results",
    "forecast_comparison_results",
    "forecast_anomaly_findings",
    "forecast_review_items",
    "forecast_evidence_packages",
]


def _migrated_db(td: str) -> str:
    db = Path(td) / "v61.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_latest_schema_version_is_at_least_62() -> None:
    assert LATEST_SCHEMA_VERSION >= 62


def test_migration_applies_v61_with_all_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert [t for t in V61_TABLES if t not in names] == []
        assert len(V61_TABLES) == 8


def test_migration_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v61.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        n61 = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=61").fetchone()[0]
        assert n61 == 1
        # Prior forecast versions still recorded.
        for v in (58, 59, 60, 61):
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version=?", (v,)
                ).fetchone()[0]
                == 1
            )
        conn.close()


def test_v61_tables_ship_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        for t in V61_TABLES:
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
        conn.close()


def test_external_forecasts_origin_defaults_to_external() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        conn.execute(
            """
            INSERT INTO forecast_external_forecasts
              (external_forecast_id, project_key, source_system, period, source_filename,
               file_sha256, content_sha256, byte_count, row_count, import_run_id,
               imported_at_utc, created_utc)
            VALUES ('ef1','tropical','excel','2026-06','f.xlsx','a','b',10,2,'r1','t','t')
            """
        )
        origin = conn.execute(
            "SELECT forecast_origin FROM forecast_external_forecasts WHERE external_forecast_id='ef1'"
        ).fetchone()[0]
        conn.close()
        assert origin == "external"


def test_lifecycle_contract_count_and_v61_classification() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == 439
    assert contract["table_count"] == len(contract["tables"])
    for t in V61_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "forecast_external_v61"
        assert entry["lifecycle_status"] == "operational_empty_expected"
        assert entry["v"] == "V61"
