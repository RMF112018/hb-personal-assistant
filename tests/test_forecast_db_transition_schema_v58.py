"""v58 — Forecast DB-transition FOUNDATION schema tests.

Covers: the v58 additive migration applies, is idempotent, records exactly one
schema_migrations row, lands ONLY the five foundation/lineage tables (no downstream
forecast-domain tables), carries the common lineage columns, preserves prior versions
(additive), and leaves the DB integrity-clean. No network, no Ollama — additive schema only.

This is Phase 1 of the construction-financial-review JSON/JSONL -> SQLite transition:
it proves schema ownership (tables live in hb_assistant/store/migrator.py), idempotency,
and lineage conventions. Domain tables are deferred to later additive migrations (v59+).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

# The five foundation tables that v58 must create — and nothing more.
V58_FOUNDATION_TABLES = [
    "forecast_projects",
    "forecast_runs",
    "forecast_source_ingestions",
    "forecast_package_manifests",
    "forecast_validation_events",
]

# Downstream forecast-domain tables must NOT be present at v58 (deferred to v59+).
V58_DEFERRED_DOMAIN_TABLES = [
    "budget_code_canonical_data",
    "cost_entry_records",
    "monthly_actuals_by_budget_code",
    "forecast_operator_controls",
    "forecast_model_controls",
    "forecast_final_monthly",
    "forecast_comprehensive_recommendations",
    "forecast_actuals_plus_forecast_monthly",
]

# Lineage columns expected on the ingestion/manifest tables.
_LINEAGE_EXPECTATIONS = {
    "forecast_source_ingestions": {
        "ingestion_id",
        "project_key",
        "run_id",
        "source_kind",
        "source_package",
        "source_sha256",
        "created_utc",
    },
    "forecast_package_manifests": {
        "package_id",
        "project_key",
        "run_id",
        "package_type",
        "package_name",
        "source_data_hashes",
        "validation_passed",
        "created_utc",
    },
    "forecast_validation_events": {
        "run_id",
        "event_seq",
        "project_key",
        "gate_name",
        "status",
        "created_utc",
    },
}


def _migrated_db(td: str) -> str:
    db = Path(td) / "v58.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _tables(db: str) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def _columns(db: str, table: str) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_latest_schema_version_is_at_least_58() -> None:
    assert LATEST_SCHEMA_VERSION >= 58


def test_migration_applies_v58_foundation_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        names = _tables(db)
        missing = [t for t in V58_FOUNDATION_TABLES if t not in names]
        assert missing == [], f"missing foundation tables: {missing}"


def test_v58_does_not_create_deferred_domain_tables() -> None:
    """Phase 1 is foundation-only; domain tables must wait for v59+."""
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        names = _tables(db)
        leaked = [t for t in V58_DEFERRED_DOMAIN_TABLES if t in names]
        assert leaked == [], f"v58 leaked deferred domain tables: {leaked}"


def test_migration_idempotent_records_single_v58_row() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v58.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        try:
            n58 = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version=58"
            ).fetchone()[0]
        finally:
            conn.close()
        assert n58 == 1


def test_foundation_tables_carry_lineage_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        for table, expected in _LINEAGE_EXPECTATIONS.items():
            cols = _columns(db, table)
            missing = expected - cols
            assert missing == set(), f"{table} missing lineage columns: {missing}"


def test_v58_preserves_prior_versions_additively() -> None:
    """v55 read-model table and the schema_migrations ledger remain intact."""
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        names = _tables(db)
        assert "procore_ep_budget_detail_rows" in names  # v55, additive coexistence
        conn = sqlite3.connect(db)
        try:
            versions = {
                r[0] for r in conn.execute("SELECT version FROM schema_migrations")
            }
        finally:
            conn.close()
        assert {55, 57, 58}.issubset(versions)


def test_migrated_db_integrity_ok() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _migrated_db(td)
        conn = sqlite3.connect(db)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()
