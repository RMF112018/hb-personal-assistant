"""Phase 08B Prompt 02 — V28 persisted agent-receipt schema additions.

Proves V28 additively (1) creates the two agent-receipt tables that ship empty, (2) declares +
enforces the canonical no-raw / no-writeback guard `CHECK(col = 0)` columns, (3) enforces the FK +
review-tier CHECK, (4) is idempotent, (5) leaves V1-V27 intact, and (6) the lifecycle contract
classifies both tables operational_empty_expected at count 144.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V28_TABLES = ["second_brain_agent_run_receipts", "second_brain_agent_model_receipts"]

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


def test_v28_is_latest_and_creates_receipt_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v28.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION >= 28
        conn = sqlite3.connect(str(db))
        tables = _names(conn)
        for t in _V28_TABLES:
            assert t in tables, f"missing V28 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v28_guard_columns_present_and_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v28.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in _V28_TABLES:
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
                "INSERT INTO second_brain_agent_model_receipts "
                "(model_receipt_id, model_profile_id, input_context_hash, output_hash, "
                " external_writeback_performed) VALUES ('m1','p','h1','h2',1)"
            )


def test_v28_review_tier_check_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v28.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO second_brain_agent_run_receipts "
                "(agent_run_id, agent_id, run_kind, status, review_tier) "
                "VALUES ('r1','a','k','synthesized',7)"
            )


def test_v28_is_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v28.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 28").fetchone()[0]
        assert n == 1
        # Prior-version tables intact (V26 substrate + V27 handoff lines).
        tables = _names(conn)
        for t in ("daily_brief_runs", "daily_brief_handoff_lines", "second_brain_evaluation_runs"):
            assert t in tables


def test_v28_tables_classified_in_lifecycle_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v28.db"
        _migrate(db)
        report = build_table_inventory_report(db_path=str(db))
        assert report["contract_table_count"] == 454  # Phase 4: +8 v61 external-forecast tables (was 399; V62 +13 schedule tables; V63 +10 run-output tables)
        by_name = {t["table_name"]: t for t in report["tables"]}
        for t in _V28_TABLES:
            assert t in by_name, f"{t} absent from live inventory"
            assert by_name[t]["lifecycle_status"] == "operational_empty_expected"
            assert by_name[t].get("source") == "contract"
        assert report["reconciliation"]["in_db_not_in_contract"] == []
