"""P-C — V73 additive migration tests (forecast generation-request contract table).

Covers: migration applies to V73 and is idempotent (prior versions preserved); the
forecast_generation_requests table is present, ships empty, and carries the required columns;
the lifecycle contract stays self-consistent and classifies the table as the v73 generation-request
family. Additive schema only — no network, no CFR, no live DB.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.forecast_generation_requests_tables import V73_TABLES
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_REQUIRED_COLUMNS = {
    "request_id",
    "run_id",
    "project_key",
    "generation_mode",
    "generator_kind",
    "forecast_start_date",
    "forecast_cutoff_date",
    "forecast_cutoff_date_basis",
    "schedule_version_key",
    "config_snapshot_id",
    "model_version_key",
    "requested_by_role",
    "request_status",
    "validation_status",
    "validation_errors_json",
    "readiness_status_at_request",
    "readiness_reasons_json",
    "created_utc",
    "updated_utc",
    "started_utc",
    "completed_utc",
    "failed_utc",
    "failure_code",
    "failure_message",
}


def _migrated_db(td: str) -> str:
    db = Path(td) / "v73.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def test_latest_schema_version_is_at_least_73() -> None:
    assert LATEST_SCHEMA_VERSION >= 73


def test_migration_applies_v73_with_table() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert [t for t in V73_TABLES if t not in names] == []
        assert len(V73_TABLES) == 1


def test_migration_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v73.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        n73 = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=73").fetchone()[0]
        assert n73 == 1
        for v in (58, 66, 72, 73):
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version=?", (v,)
                ).fetchone()[0]
                == 1
            )
        conn.close()


def test_v73_table_ships_empty_with_required_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        assert conn.execute("SELECT COUNT(*) FROM forecast_generation_requests").fetchone()[0] == 0
        cols = {r[1] for r in conn.execute("PRAGMA table_info(forecast_generation_requests)")}
        conn.close()
        assert _REQUIRED_COLUMNS - cols == set()


def test_lifecycle_contract_self_consistent_and_v73_classification() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == len(contract["tables"])
    for t in V73_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "forecast_generation_request_v73"
        assert entry["lifecycle_status"] == "operational_empty_expected"
        assert entry["v"] == "V73"
