"""Phase 08B Prompt 05 — V29 run-registry + run-step ledger schema additions.

Proves V29 additively (1) creates the run registry + run-step tables that ship empty, (2) declares
+ enforces the canonical no-raw / no-writeback guard `CHECK(col = 0)` columns, (3) enforces the
run-step -> registry FK, (4) is idempotent, (5) leaves V1-V28 intact, and (6) the lifecycle
contract classifies both tables operational_empty_expected at count 146.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V29_TABLES = ["second_brain_run_registry", "second_brain_run_steps"]

_GUARD_NAME_RE = re.compile(
    r"(raw_email_body_persisted|raw_document_text_persisted|raw_calendar_payload_persisted|"
    r"raw_prompt_persisted|raw_response_persisted|retrieved_context_persisted|"
    r"signed_url_persisted|download_url_persisted|external_writeback_performed)"
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


def test_v29_is_latest_and_creates_run_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v29.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert LATEST_SCHEMA_VERSION >= 29
        conn = sqlite3.connect(str(db))
        tables = _names(conn)
        for t in _V29_TABLES:
            assert t in tables, f"missing V29 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v29_guard_columns_present_and_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v29.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in _V29_TABLES:
            guards = set(_GUARD_NAME_RE.findall(_ddl(conn, t)))
            for col in (
                "raw_prompt_persisted",
                "raw_response_persisted",
                "signed_url_persisted",
                "download_url_persisted",
                "external_writeback_performed",
            ):
                assert col in guards, f"{t} missing guard {col}"
        # The guard CHECK(col = 0) rejects a nonzero write.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO second_brain_run_registry "
                "(run_registry_id, run_kind, status, external_writeback_performed) "
                "VALUES ('r1','daily_brief','started',1)"
            )


def test_v29_run_step_fk_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v29.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO second_brain_run_steps "
                "(run_step_id, run_registry_id, step_name, step_order, status) "
                "VALUES ('s1','does-not-exist','lock','0','ok')"
            )


def test_v29_is_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v29.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 29").fetchone()[0]
        assert n == 1
        # Prior-version tables intact (V1 ledger + V27/V28 second-brain substrate).
        tables = _names(conn)
        for t in (
            "assistant_runs",
            "daily_brief_handoff_lines",
            "second_brain_agent_run_receipts",
        ):
            assert t in tables


def test_v29_tables_classified_in_lifecycle_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v29.db"
        _migrate(db)
        report = build_table_inventory_report(db_path=str(db))
        assert report["contract_table_count"] == 441  # Phase 4: +8 v61 external-forecast tables (was 399; V62 +13 schedule tables; V63 +10 run-output tables)
        by_name = {t["table_name"]: t for t in report["tables"]}
        for t in _V29_TABLES:
            assert t in by_name, f"{t} absent from live inventory"
            assert by_name[t]["lifecycle_status"] == "operational_empty_expected"
            assert by_name[t].get("source") == "contract"
        assert report["reconciliation"]["in_db_not_in_contract"] == []
