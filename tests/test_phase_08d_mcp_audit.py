"""Phase 08D Prompt 10 — MCP audit / permission agent.

Proves the audit agent snapshots all four registries, runs the ten permission-audit checks
(all passing), persists a metadata-only permission-audit run, and attests metadata-only
receipts. Read-only and guard-clean throughout.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.mcp import (
    run_mcp_permission_audit,
    snapshot_all_registries,
    snapshot_tool_registry,
)

_EXPECTED_CHECKS = {
    "server_config_safe",
    "allowed_registry_safe",
    "denied_registry_complete",
    "resources_safe",
    "prompts_safe",
    "receipts_metadata_only",
    "claude_config_safe",
    "no_raw_access",
    "no_writeback",
    "no_direct_apis",
}


def test_tool_registry_snapshot_is_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "a.db")
        sid = snapshot_tool_registry(db_path=db, persist=True)
        assert sid
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT allowed_tool_count, denied_action_count, registry_hash, "
            "external_writeback_performed, raw_prompt_persisted "
            "FROM second_brain_mcp_tool_registry_snapshots"
        ).fetchone()
        allowed, denied, reg_hash, ext_wb, raw_prompt = row
        assert (allowed, denied) == (9, 27)
        assert reg_hash and (ext_wb, raw_prompt) == (0, 0)


def test_snapshot_all_registries_persists_four_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "a.db")
        ids = snapshot_all_registries(db_path=db, persist=True)
        assert all(ids[k] for k in ("server_config", "tool_registry", "resource_registry", "prompt_registry"))
        conn = sqlite3.connect(db)
        for table in (
            "second_brain_mcp_server_config_snapshots",
            "second_brain_mcp_tool_registry_snapshots",
            "second_brain_mcp_resource_registry_snapshots",
            "second_brain_mcp_prompt_registry_snapshots",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1


def test_permission_audit_passes_all_ten_checks() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "a.db")
        report = run_mcp_permission_audit(db_path=db, evidence_dir=td, persist=True, write_evidence=True)
        assert report["proof_passed"] is True
        assert report["status"] == "ok"
        assert report["finding_count"] == 0
        names = {c["name"] for c in report["checks"]}
        assert names == _EXPECTED_CHECKS
        assert all(c["passed"] for c in report["checks"])
        assert report["receipts"]["metadata_only"] is True
        assert (Path(td) / "mcp-audit-receipt-proof.json").exists()


def test_permission_audit_run_persists_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "a.db")
        report = run_mcp_permission_audit(db_path=db, persist=True, write_evidence=False)
        assert report["audit_run_id"]
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT status, finding_count, checks_json, external_writeback_performed, "
            "raw_prompt_persisted FROM second_brain_mcp_permission_audit_runs"
        ).fetchone()
        status, findings, checks_json, ext_wb, raw_prompt = row
        assert (status, findings) == ("ok", 0)
        assert len(json.loads(checks_json)) == 10
        assert (ext_wb, raw_prompt) == (0, 0)
