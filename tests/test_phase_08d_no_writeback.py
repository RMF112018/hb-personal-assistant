"""Phase 08D Prompt 14 — no-MCP-writeback proof.

Proves the deterministic, read-only scan over the MCP surfaces (permission policy, denied
registry, tool wrappers, receipts, config preview, server guardrails, and the committed
evidence artifacts) finds no writeback / direct-API / external-delivery capability; that the
proof writes a guard-clean JSON+MD artifact; that the server startup check now passes
(dropping the prompt-14 serve blocker so only the optional MCP SDK remains); and that the
Phase 08D gate 12 flips to pass. Read-only and static throughout — the workflow tools are
never dispatched.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.data_quality import (
    evaluate_phase_08d_data_quality_gates,
)
from hb_assistant.construction.second_brain.mcp import build_mcp_status
from hb_assistant.construction.second_brain.mcp.proof import (
    _receipts_no_writeback,
    build_no_mcp_writeback_proof,
    evaluate_no_writeback_mcp_access,
)

runner = CliRunner()


def test_evaluator_passes_all_surfaces() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = evaluate_no_writeback_mcp_access(db_path=str(Path(td) / "a.db"))
    assert report["proof_passed"] is True
    surfaces = {s["surface"] for s in report["surfaces"]}
    assert {
        "permission_policy",
        "denied_registry",
        "tool_wrappers",
        "receipts",
        "config_preview",
        "server_guardrails",
        "evidence",
    } <= surfaces
    assert all(s["passed"] for s in report["surfaces"])


def test_permission_policy_all_allow_flags_false() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = evaluate_no_writeback_mcp_access(
            db_path=str(Path(td) / "a.db"), include_server_status=False, include_evidence_scan=False
        )
    perm = next(s for s in report["surfaces"] if s["surface"] == "permission_policy")
    assert perm["passed"] is True
    denied = next(s for s in report["surfaces"] if s["surface"] == "denied_registry")
    assert denied["passed"] is True
    assert denied["missing"] == []


def test_receipts_guard_columns_present_and_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        result = _receipts_no_writeback(db_path=str(Path(td) / "a.db"))
    assert result["passed"] is True
    assert result["writeback_guard_columns_present"] is True
    assert result["guard_columns_zero"] is True


def test_config_preview_never_auto_applies() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = evaluate_no_writeback_mcp_access(
            db_path=str(Path(td) / "a.db"), include_server_status=False, include_evidence_scan=False
        )
    cfg = next(s for s in report["surfaces"] if s["surface"] == "config_preview")
    assert cfg["auto_apply"] is False
    assert cfg["preview_only_no_auto_apply"] is True
    assert cfg["passed"] is True


def test_build_proof_writes_guard_clean_artifacts() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_no_mcp_writeback_proof(
            db_path=str(Path(td) / "a.db"), evidence_dir=td, write_evidence=True
        )
        assert proof["proof_passed"] is True
        assert proof["proof"] == "phase_08d_no_mcp_writeback"
        json_path = Path(td) / "no-mcp-writeback-proof.json"
        md_path = Path(td) / "no-mcp-writeback-proof.md"
        assert json_path.exists() and md_path.exists()
        reloaded = json.loads(json_path.read_text())
        assert reloaded["proof_passed"] is True
        assert reloaded["guardrails"]["no_external_writeback"] is True
        assert "passed: true" in md_path.read_text().lower()


def test_startup_check_passes_and_drops_prompt_14_blocker() -> None:
    with tempfile.TemporaryDirectory() as td:
        status = build_mcp_status(db_path=str(Path(td) / "a.db"), persist=False)
    by_name = {c["name"]: c["status"] for c in status["checks"]}
    assert by_name["no_writeback_proof"] == "pass"
    assert by_name["no_raw_access_proof"] == "pass"
    assert "no_writeback_proof_pending_prompt_14" not in status["serve_blockers"]
    # After Prompt 14 the only possible serve blocker is the optional MCP SDK (Prompt 15):
    # absent → fail-closed; installed → ready_to_serve.
    if importlib.util.find_spec("mcp") is not None:
        assert status["serve_blockers"] == []
        assert status["ready_to_serve"] is True
    else:
        assert status["serve_blockers"] == ["mcp_sdk_not_installed"]
        assert status["ready_to_serve"] is False


def test_data_quality_gate_no_writeback_now_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = evaluate_phase_08d_data_quality_gates(db_path=str(Path(td) / "a.db"))
    assert report["by_field_status"]["no_writeback"] == "pass"
    assert "no_mcp_writeback_proof_pending_prompt_14" not in report["serve_blockers"]
    if importlib.util.find_spec("mcp") is not None:
        assert report["ready_to_serve"] is True
        assert report["serve_blockers"] == []
    else:
        assert report["ready_to_serve"] is False
        assert report["serve_blockers"] == ["mcp_sdk_not_installed"]


def test_cli_no_writeback_emits_passing_proof() -> None:
    result = runner.invoke(app, ["second-brain", "mcp", "no-writeback", "--no-evidence", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["proof_passed"] is True
    assert payload["proof"] == "phase_08d_no_mcp_writeback"
