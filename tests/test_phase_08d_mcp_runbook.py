"""Phase 08D Prompt 09 — Claude Desktop config + runbook.

Proves the generated config preview is safe / schema-conformant / preview-only, that no mcp
code path references the live Claude Desktop config (so it is never auto-written), that the
runbook proof passes, and that the operator runbook documents the five steps + the
no-auto-write warning + the live config path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.mcp import (
    build_claude_desktop_config_preview,
    build_mcp_claude_desktop_runbook_proof,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUNBOOK = _REPO_ROOT / "docs" / "runbooks" / "phase-08d-claude-desktop-configuration-runbook.md"


def test_config_preview_is_safe_and_preview_only() -> None:
    preview = build_claude_desktop_config_preview(persist=False, write_evidence=False)
    assert preview["safe"] is True
    assert preview["schema_conformant"] is True
    assert preview["transport"] == "stdio"
    assert preview["unsafe_reasons"] == []
    assert preview["auto_apply"] is False


def test_no_mcp_code_references_the_live_claude_config() -> None:
    proof = build_mcp_claude_desktop_runbook_proof(write_evidence=False)
    assert proof["no_auto_write"]["live_config_never_written"] is True
    assert proof["no_auto_write"]["findings"] == []
    assert proof["no_auto_write"]["mcp_files_scanned"] >= 5


def test_runbook_proof_passes_and_writes_evidence() -> None:
    with tempfile.TemporaryDirectory() as td:
        proof = build_mcp_claude_desktop_runbook_proof(evidence_dir=td, write_evidence=True)
        assert proof["proof_passed"] is True
        assert len(proof["operator_runbook_steps"]) == 5
        assert proof["safe_checklist"]["manual_paste_only"] is True
        assert (Path(td) / "mcp-claude-desktop-runbook-proof.json").exists()


def test_operator_runbook_documents_steps_and_no_auto_write() -> None:
    text = _RUNBOOK.read_text(encoding="utf-8")
    assert "claude_desktop_config.json" in text  # live path, for manual paste
    assert "never writes" in text or "never auto-written" in text or "never auto-write" in text
    assert "config-preview --client claude-desktop" in text
    assert "mcp audit" in text
