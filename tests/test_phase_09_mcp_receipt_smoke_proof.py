"""Phase 09 Prompt 04 — MCP runtime receipt & denial smoke proof tests.

Exercises ``build_mcp_receipt_smoke_proof`` over an in-process allowed/denied broker smoke
(no MCP SDK, no external call, receipts written to a temp DB): a normal guard-clean
population, the missing-wrapper fail-closed path, the unsafe-output (no-raw) fail-closed
path, and empty / stale-schema databases.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.construction.second_brain.mcp import ToolBroker, build_default_broker
from hb_assistant.construction.second_brain.mcp.receipt_smoke_proof import (
    build_mcp_receipt_smoke_proof,
)
from hb_assistant.store.migrator import SQLiteMigrator


def _raw_leaking_wrapper(_args: dict[str, Any]) -> dict[str, Any]:
    # Tries to leak a forbidden raw pattern (a URL) — the broker must block it.
    return {"status": "ok", "results": [{"link": "https://example.com/raw"}]}


def test_normal_smoke_is_guard_clean_and_populated(tmp_path: Path) -> None:
    db = str(tmp_path / "proof.sqlite3")
    SQLiteMigrator(db).apply()
    broker = build_default_broker(db_path=db, persist=True)
    assert broker.dispatch("hb_status", {})["decision"] == "allowed"
    for denied in ("arbitrary_sql", "graph_api_call", "email_send"):
        assert broker.dispatch(denied, {})["decision"] == "denied"

    proof = build_mcp_receipt_smoke_proof(db)
    assert proof["proof_passed"] is True
    assert proof["populated"] is True
    assert proof["allowed_receipt_count"] >= 1
    assert proof["denial_receipt_count"] >= 3
    assert proof["guard_columns_zero"]["second_brain_mcp_tool_call_receipts"] is True
    assert proof["guard_columns_zero"]["second_brain_mcp_denial_receipts"] is True
    assert proof["tool_call_decisions_ok"] is True
    assert proof["denial_decisions_ok"] is True
    assert proof["allowed_tools_valid"] is True
    assert proof["denials_missing_reason"] == 0
    assert proof["raw_content_findings"] == []


def test_missing_wrapper_denies_allowed_tool(tmp_path: Path) -> None:
    db = str(tmp_path / "nowrap.sqlite3")
    SQLiteMigrator(db).apply()
    broker = ToolBroker(wrappers={}, db_path=db, persist=True)
    env = broker.dispatch("hb_status", {})
    assert env["decision"] == "denied"  # WRAPPER_UNAVAILABLE — never executed

    proof = build_mcp_receipt_smoke_proof(db)
    # A denial was recorded but no allowed receipt → not a complete smoke, still guard-clean.
    assert proof["allowed_receipt_count"] == 0
    assert proof["denial_receipt_count"] >= 1
    assert proof["populated"] is False
    assert proof["guard_columns_zero"]["second_brain_mcp_denial_receipts"] is True


def test_unsafe_output_is_denied_no_raw_persisted(tmp_path: Path) -> None:
    db = str(tmp_path / "unsafe.sqlite3")
    SQLiteMigrator(db).apply()
    broker = ToolBroker(wrappers={"hb_status": _raw_leaking_wrapper}, db_path=db, persist=True)
    env = broker.dispatch("hb_status", {})
    assert env["decision"] == "denied"  # UNSAFE_OUTPUT — the URL never leaks

    proof = build_mcp_receipt_smoke_proof(db)
    # The unsafe call became a denial; no allowed receipt, guard-clean, no raw findings.
    assert proof["allowed_receipt_count"] == 0
    assert proof["denial_receipt_count"] >= 1
    assert proof["raw_content_findings"] == []
    assert proof["guard_columns_zero"]["second_brain_mcp_denial_receipts"] is True


def test_empty_db_is_not_populated(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.sqlite3")
    SQLiteMigrator(db).apply()
    proof = build_mcp_receipt_smoke_proof(db)
    assert proof["populated"] is False
    assert proof["proof_passed"] is False
    assert proof["allowed_receipt_count"] == 0
    assert proof["denial_receipt_count"] == 0


def test_stale_schema_reports_missing_tables(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite3")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_mcp_receipt_smoke_proof(db)
    assert proof["schema_version"] == 5
    assert proof["proof_passed"] is False
    assert proof["populated"] is False
    assert "second_brain_mcp_tool_call_receipts" in proof["missing_tables"]
    assert "second_brain_mcp_denial_receipts" in proof["missing_tables"]
