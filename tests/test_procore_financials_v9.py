"""Phase 05 V9 billing/subcontractor-invoice migration tests.

Proves V9 applies additively on top of V8, creates the billing-period + subcontractor
-invoice header tables + indexes, is idempotent, leaves V1-V8 intact, and that the
redaction-guard CHECK constraints reject raw persistence.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import SQLiteMigrator

_V9_TABLES = {
    "procore_financial_billing_periods",
    "procore_financial_subcontractor_invoices",
}

_V9_INDEXES = {
    "ix_procore_financial_billing_periods_project_status",
    "ix_procore_financial_subcontractor_invoices_project_filters",
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


def test_v9_applies_from_empty_db_and_creates_billing_tables() -> None:
    db = _temp_db()
    assert _migrate(db) == 11  # full migrator now reaches v11 (Phase 06)
    tables = _names(db, "table")
    assert not (_V9_TABLES - tables), f"V9 tables missing: {sorted(_V9_TABLES - tables)}"
    indexes = _names(db, "index")
    assert not (_V9_INDEXES - indexes), f"V9 indexes missing: {sorted(_V9_INDEXES - indexes)}"


def test_v9_leaves_v1_v8_tables_intact() -> None:
    db = _temp_db()
    assert _migrate(db) == 11  # full migrator now reaches v11 (Phase 06)
    tables = _names(db, "table")
    assert "source_records" in tables  # V1 core
    assert {"procore_live_records", "procore_action_signals"} <= tables  # V6/V7
    # V8 financial tables (incl. the invoice-items table reused by V9 projections).
    assert {"procore_financial_contracts", "procore_financial_invoice_items"} <= tables


def test_v9_is_idempotent() -> None:
    db = _temp_db()
    assert _migrate(db) == 11  # full migrator now reaches v11 (Phase 06)
    assert _migrate(db) == 11  # full migrator now reaches v11 (Phase 06)
    conn = sqlite3.connect(str(db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 9"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_v9_check_constraints_reject_raw_persistence() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO procore_financial_subcontractor_invoices "
                "(record_key, project_key, endpoint_id, invoice_id, raw_body_persisted) "
                "VALUES ('k', 'tropical', 'subcontractor-invoices', '1', 1)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO procore_financial_billing_periods "
                "(billing_period_key, project_key, endpoint_id, billing_period_id, redaction_applied) "
                "VALUES ('k', 'tropical', 'billing-periods', '1', 0)"
            )
    finally:
        conn.close()
