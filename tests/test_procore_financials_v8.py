"""Phase 05 V8 financial-schema migration tests.

Proves V8 applies from an empty DB, leaves V1-V7 intact, is idempotent, and that
the redaction-guard CHECK constraints reject raw persistence.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import SQLiteMigrator

_V8_TABLES = {
    "procore_financial_contracts",
    "procore_financial_line_items",
    "procore_financial_change_orders",
    "procore_financial_payment_applications",
    "procore_financial_invoice_items",
    "procore_financial_rfqs",
    "procore_financial_change_events",
    "procore_financial_budget_views",
    "procore_financial_budget_rows",
    "procore_financial_amount_facts",
    # HB-authored extension tables (beyond the authoritative package SQL).
    "procore_financial_change_order_line_items",
    "procore_financial_budget_changes",
    "procore_financial_compliance_documents",
}

_V8_INDEXES = {
    "ix_procore_financial_contracts_project_family",
    "ix_procore_financial_line_items_parent",
    "ix_procore_financial_change_orders_project_status",
    "ix_procore_financial_amount_facts_project_name",
    "ix_procore_financial_change_order_line_items_parent",
    "ix_procore_financial_budget_changes_project_kind",
    "ix_procore_financial_compliance_documents_project_status",
}


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(db: Path, kind: str) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        return {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type=?", (kind,))
        }
    finally:
        conn.close()


def test_v8_applies_from_empty_db_and_creates_all_tables() -> None:
    db = _temp_db()
    assert _migrate(db) == 19  # full migrator now reaches v15 (Phase 06 files)
    tables = _names(db, "table")
    missing = _V8_TABLES - tables
    assert not missing, f"V8 tables missing: {sorted(missing)}"
    indexes = _names(db, "index")
    missing_idx = _V8_INDEXES - indexes
    assert not missing_idx, f"V8 indexes missing: {sorted(missing_idx)}"


def test_v8_leaves_v1_v7_tables_intact() -> None:
    db = _temp_db()
    assert _migrate(db) == 19  # full migrator now reaches v15 (Phase 06 files)
    tables = _names(db, "table")
    # V1 core, V6 live-sync, V7 history all still present alongside V8.
    assert "source_records" in tables
    assert {"procore_live_records", "procore_live_sync_runs"} <= tables
    assert {"procore_live_record_snapshots", "procore_action_signals"} <= tables


def test_v8_is_idempotent() -> None:
    db = _temp_db()
    assert _migrate(db) == 19  # full migrator now reaches v15 (Phase 06 files)
    assert _migrate(db) == 19  # full migrator now reaches v15 (Phase 06 files)
    conn = sqlite3.connect(str(db))
    try:
        count = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 8").fetchone()[
            0
        ]
    finally:
        conn.close()
    assert count == 1


def test_v8_check_rejects_raw_body_persisted() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO procore_financial_contracts (
                  record_key, project_key, endpoint_id, contract_id, contract_family,
                  raw_body_persisted
                ) VALUES ('rk1', 'tropical', 'prime-contracts', '1', 'owner', 1)
                """
            )
    finally:
        conn.close()


def test_v8_check_rejects_redaction_not_applied() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO procore_financial_contracts (
                  record_key, project_key, endpoint_id, contract_id, contract_family,
                  redaction_applied
                ) VALUES ('rk1', 'tropical', 'prime-contracts', '1', 'owner', 0)
                """
            )
    finally:
        conn.close()


def test_v8_amount_facts_check_rejects_raw_body() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO procore_financial_amount_facts (
                  amount_fact_id, project_key, record_key, endpoint_id, amount_name,
                  amount_value, source_field_path, created_at_utc, raw_body_persisted
                ) VALUES ('af1', 'tropical', 'rk1', 'prime-contracts', 'grand_total',
                  '1.00', 'procore_financial_contracts.grand_total',
                  '2026-01-01T00:00:00Z', 1)
                """
            )
    finally:
        conn.close()
