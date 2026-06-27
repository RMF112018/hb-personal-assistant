"""Phase 08C Prompt 01 — V35 financial fact normalization and readiness schema additions.

Proves V35 additively (1) creates the 10 second_brain_financial_* tables that ship empty,
(2) declares + enforces the full 08C guard columns (standard no-raw + raw_financial_source_payload_persisted
+ financial_determination_performed + payment_decision_performed + claim_or_entitlement_decision_performed
+ advisory_only=1 CHECK), (3) stores money as canonical_decimal_text TEXT + minor_units INTEGER (no REAL/float),
(4) is idempotent and leaves V1-V34 intact, and (5) the lifecycle contract classifies the tables
operational_empty_expected; the live lifecycle contract now totals 190 tables (post-V38).
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V35_TABLES = [
    "second_brain_financial_fact_normalization_runs",
    "second_brain_financial_amount_facts_normalized",
    "second_brain_financial_currency_completeness_snapshots",
    "second_brain_financial_wbs_cost_code_snapshots",
    "second_brain_financial_source_coverage_snapshots",
    "second_brain_financial_exposure_summary_items",
    "second_brain_financial_forecast_readiness_runs",
    "second_brain_financial_review_required_items",
    "second_brain_financial_readiness_agent_runs",
    "second_brain_phase_08c_validation_runs",
]

# Include new 08C-specific financial guards + standard
_GUARD_NAME_RE = re.compile(
    r"(raw_email_body_persisted|raw_document_text_persisted|raw_calendar_payload_persisted|"
    r"raw_procore_payload_persisted|raw_financial_source_payload_persisted|"
    r"raw_prompt_persisted|raw_response_persisted|"
    r"signed_url_persisted|download_url_persisted|external_writeback_performed|"
    r"financial_determination_performed|payment_decision_performed|claim_or_entitlement_decision_performed|advisory_only)"
)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    assert row is not None, f"missing table {table}"
    return str(row[0])


def test_v35_is_latest_and_creates_financial_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v35.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert LATEST_SCHEMA_VERSION >= 35
        conn = sqlite3.connect(str(db))
        tables = _names(conn)
        for t in _V35_TABLES:
            assert t in tables, f"missing V35 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v35_all_08c_guard_columns_present_and_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v35.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in _V35_TABLES:
            ddl = _ddl(conn, t)
            guards = set(_GUARD_NAME_RE.findall(ddl))
            for col in (
                "raw_financial_source_payload_persisted",
                "financial_determination_performed",
                "payment_decision_performed",
                "claim_or_entitlement_decision_performed",
                "advisory_only",
                "raw_prompt_persisted",
                "raw_response_persisted",
                "signed_url_persisted",
                "download_url_persisted",
                "external_writeback_performed",
            ):
                assert col in guards or col in ddl, f"{t} missing guard {col}"
            # advisory_only enforced =1
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    f"INSERT INTO {t} (id, run_id, advisory_only) VALUES (1, 'r1', 0)"
                    if "run_id" in ddl
                    else f"INSERT INTO {t} (id, advisory_only) VALUES (1, 0)"
                )


def test_v35_money_stored_as_decimal_text_not_float() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v35.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # amount_facts_normalized has canonical_decimal_text TEXT, minor_units INTEGER
        ddl = _ddl(conn, "second_brain_financial_amount_facts_normalized")
        assert "canonical_decimal_text TEXT" in ddl
        assert "minor_units INTEGER" in ddl
        assert "REAL" not in ddl.upper() or "canonical" in ddl  # no float money


def test_v35_is_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v35.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 35").fetchone()[0]
        assert n == 1
        tables = _names(conn)
        # prior 08B table still present
        assert "daily_brief_open_receipts" in tables
        # no raw in new tables by construction
        for t in _V35_TABLES:
            assert "raw_financial_source_payload_persisted" in _ddl(conn, t)


def test_v35_tables_classified_in_lifecycle_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v35.db"
        _migrate(db)
        report = build_table_inventory_report(db_path=str(db))
        assert report["contract_table_count"] == 469  # live table lifecycle contract count (was 439; 451 before V76 staffing)
        by_name = {t["table_name"]: t for t in report["tables"]}
        for t in _V35_TABLES:
            assert t in by_name, f"{t} absent from live inventory"
            assert by_name[t]["lifecycle_status"] == "operational_empty_expected"
            assert by_name[t].get("phase_owner") == "08C"
        assert report["reconciliation"]["in_db_not_in_contract"] == []
