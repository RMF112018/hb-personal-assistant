"""Phase 08D Prompt 02 — V37 local MCP bridge metadata substrate schema additions.

Proves V37 additively (1) creates the ten second_brain_mcp_* / phase_08d tables that ship
empty, (2) declares + enforces the full twenty no-raw / no-writeback / no-direct-api /
no-determination guard columns CHECK(... = 0) on every table, (3) stores only metadata
(hashes/counts/status/reason codes) on the receipt tables — no raw argument/result/content
columns, (4) is idempotent and leaves V1-V36 intact, and (5) the lifecycle contract
classifies the ten tables operational_empty_expected / phase_owner 08D; the live lifecycle contract now totals 190 tables (post-V38).

No server, broker, or runtime dispatch is exercised here — the substrate is schema-only.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V37_TABLES = [
    "second_brain_mcp_server_config_snapshots",
    "second_brain_mcp_tool_registry_snapshots",
    "second_brain_mcp_resource_registry_snapshots",
    "second_brain_mcp_prompt_registry_snapshots",
    "second_brain_mcp_tool_call_receipts",
    "second_brain_mcp_denial_receipts",
    "second_brain_mcp_permission_audit_runs",
    "second_brain_mcp_policy_gate_runs",
    "second_brain_mcp_claude_desktop_config_previews",
    "second_brain_phase_08d_validation_runs",
]

# The twenty guard columns required (CHECK(... = 0)) on every V37 table.
_V37_GUARDS = [
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_financial_source_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_api_call_performed",
    "procore_api_call_performed",
    "email_send_performed",
    "calendar_update_performed",
    "source_system_writeback_performed",
    "arbitrary_sql_performed",
    "raw_store_access_performed",
    "financial_determination_performed",
    "payment_decision_performed",
    "claim_or_entitlement_decision_performed",
]


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


def test_v37_is_latest_and_creates_mcp_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v37.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert LATEST_SCHEMA_VERSION >= 37
        conn = sqlite3.connect(str(db))
        tables = _names(conn)
        for t in _V37_TABLES:
            assert t in tables, f"missing V37 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v37_all_twenty_guard_columns_present_and_check_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v37.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in _V37_TABLES:
            ddl = _ddl(conn, t)
            for guard in _V37_GUARDS:
                # column declared with a fail-closed CHECK(<guard> = 0)
                assert re.search(rf"\b{guard}\b", ddl), f"{t} missing guard column {guard}"
                assert re.search(rf"CHECK\({guard} = 0\)", ddl), f"{t} guard {guard} not CHECK(=0)"


def test_v37_receipt_tables_are_metadata_only_no_raw_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v37.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # Receipts persist hashes only, never raw arguments / results / requested content.
        call_ddl = _ddl(conn, "second_brain_mcp_tool_call_receipts")
        assert "args_hash" in call_ddl and "result_hash" in call_ddl
        denial_ddl = _ddl(conn, "second_brain_mcp_denial_receipts")
        assert "request_hash" in denial_ddl
        for ddl in (call_ddl, denial_ddl):
            for forbidden in ("raw_args", "raw_result", "raw_requested_content", "raw_prompt_text"):
                assert forbidden not in ddl, f"receipt table must not store {forbidden}"


def test_v37_guard_and_decision_checks_are_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v37.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # A fully-specified, guard-clean receipt inserts fine.
        conn.execute(
            "INSERT INTO second_brain_mcp_tool_call_receipts "
            "(receipt_id, tool_name, decision, policy_version, schema_version) "
            "VALUES ('r-ok', 'hb_status', 'allowed', 'v1', 37)"
        )
        # Flipping any guard to 1 trips the CHECK(... = 0).
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO second_brain_mcp_tool_call_receipts "
                "(receipt_id, tool_name, decision, policy_version, schema_version, raw_prompt_persisted) "
                "VALUES ('r-bad', 'hb_status', 'allowed', 'v1', 37, 1)"
            )
        # tool-call decision is constrained to allowed/denied.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO second_brain_mcp_tool_call_receipts "
                "(receipt_id, tool_name, decision, policy_version, schema_version) "
                "VALUES ('r-enum', 'hb_status', 'maybe', 'v1', 37)"
            )
        # denial receipts are pinned to decision = 'denied'.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO second_brain_mcp_denial_receipts "
                "(receipt_id, requested_action, decision, denial_reason_code, policy_version, schema_version) "
                "VALUES ('d-bad', 'arbitrary_sql', 'allowed', 'DENY_RAW', 'v1', 37)"
            )


def test_v37_is_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v37.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 37").fetchone()[0]
        assert n == 1
        tables = _names(conn)
        # prior 08C + 08B tables still present (V1-V36 untouched)
        assert "second_brain_financial_review_required_items" in tables
        assert "daily_brief_open_receipts" in tables


def test_v37_tables_classified_in_lifecycle_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v37.db"
        _migrate(db)
        report = build_table_inventory_report(db_path=str(db))
        assert report["contract_table_count"] == 437  # Phase 4: +8 v61 external-forecast tables (was 399; V62 +13 schedule tables; V63 +10 run-output tables)
        by_name = {t["table_name"]: t for t in report["tables"]}
        for t in _V37_TABLES:
            assert t in by_name, f"{t} absent from live inventory"
            assert by_name[t]["lifecycle_status"] == "operational_empty_expected"
            assert by_name[t].get("phase_owner") == "08D"
        assert report["reconciliation"]["in_db_not_in_contract"] == []
