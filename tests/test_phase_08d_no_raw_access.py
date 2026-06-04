"""Phase 08D Prompt 13 — no-raw MCP access proof.

Proves the deterministic, read-only scan over every MCP surface (registries, resources,
prompts, receipts, config preview, server status, and the committed evidence artifacts)
finds no raw-content exposure; that the proof writes a guard-clean JSON+MD artifact; that
the server startup check now passes (dropping the prompt-13 serve blocker) while the
no-writeback blocker remains; and that the Phase 08D gate 11 flips to pass. Read-only and
static throughout — the synthesis/retrieval workflow tools are never dispatched.
"""

from __future__ import annotations

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
    _receipts_no_raw,
    _scan_no_raw,
    build_no_raw_mcp_access_proof,
    evaluate_no_raw_mcp_access,
)

runner = CliRunner()


def test_evaluator_passes_all_surfaces() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = evaluate_no_raw_mcp_access(db_path=str(Path(td) / "a.db"))
    assert report["proof_passed"] is True
    surfaces = {s["surface"] for s in report["surfaces"]}
    assert {
        "registries",
        "resources",
        "prompts",
        "receipts",
        "config_preview",
        "server_status",
        "evidence",
    } <= surfaces
    assert all(s["passed"] for s in report["surfaces"])


def test_receipts_are_hash_only_no_raw_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        result = _receipts_no_raw(db_path=str(Path(td) / "a.db"))
    assert result["passed"] is True
    assert result["no_raw_columns"] is True
    assert result["hash_columns_present"] is True
    assert result["guard_columns_zero"] is True


def test_config_preview_persists_no_env_values() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = evaluate_no_raw_mcp_access(
            db_path=str(Path(td) / "a.db"), include_server_status=False, include_evidence_scan=False
        )
    cfg = next(s for s in report["surfaces"] if s["surface"] == "config_preview")
    assert cfg["env_values_persisted"] is False
    assert cfg["config_safe"] is True
    assert cfg["passed"] is True


def test_scan_flags_a_planted_raw_pattern() -> None:
    bad = _scan_no_raw("planted", {"link": "https://example.com/secret"})
    assert bad["passed"] is False
    good = _scan_no_raw("clean", {"summary": "metadata only", "count": 3})
    assert good["passed"] is True


def test_build_proof_writes_guard_clean_artifacts() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_no_raw_mcp_access_proof(
            db_path=str(Path(td) / "a.db"), evidence_dir=td, write_evidence=True
        )
        assert proof["proof_passed"] is True
        assert proof["proof"] == "phase_08d_no_raw_mcp_access"
        json_path = Path(td) / "no-raw-mcp-access-proof.json"
        md_path = Path(td) / "no-raw-mcp-access-proof.md"
        assert json_path.exists() and md_path.exists()
        reloaded = json.loads(json_path.read_text())
        assert reloaded["proof_passed"] is True
        assert reloaded["guardrails"]["no_raw_content"] is True
        assert "passed: true" in md_path.read_text().lower()


def test_startup_check_passes_and_drops_prompt_13_blocker() -> None:
    with tempfile.TemporaryDirectory() as td:
        status = build_mcp_status(db_path=str(Path(td) / "a.db"), persist=False)
    by_name = {c["name"]: c["status"] for c in status["checks"]}
    assert by_name["no_raw_access_proof"] == "pass"
    assert by_name["no_writeback_proof"] == "deferred"
    assert "no_raw_access_proof_pending_prompt_13" not in status["serve_blockers"]
    assert "no_writeback_proof_pending_prompt_14" in status["serve_blockers"]
    assert status["ready_to_serve"] is False


def test_data_quality_gate_no_raw_access_now_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = evaluate_phase_08d_data_quality_gates(db_path=str(Path(td) / "a.db"))
    assert report["by_field_status"]["no_raw_access"] == "pass"
    assert report["ready_to_serve"] is False
    assert "no_raw_access_proof_pending_prompt_13" not in report["serve_blockers"]


def test_cli_no_raw_access_emits_passing_proof() -> None:
    result = runner.invoke(app, ["second-brain", "mcp", "no-raw-access", "--no-evidence", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["proof_passed"] is True
    assert payload["proof"] == "phase_08d_no_raw_mcp_access"
