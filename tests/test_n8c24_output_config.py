"""N8C-24 — config + gate posture for the client-output workspace."""

from __future__ import annotations

import pytest

from hb_assistant.nas_mcp import profile as p
from hb_assistant.nas_mcp.config import (
    DEFAULT_CLIENT_OUTPUT_WRITE_EXTENSIONS,
    DENIED_OUTPUT_EXTENSIONS,
    NasMcpConfig,
)
from hb_assistant.nas_mcp.root_policy import READ_WRITE_ROOTS


def test_client_output_extensions_include_all_required() -> None:
    for ext in ("txt", "md", "csv", "json", "docx", "xlsx", "pptx", "pdf", "html", "zip"):
        assert ext in DEFAULT_CLIENT_OUTPUT_WRITE_EXTENSIONS
    for bad in ("sh", "exe", "py", "js", "ps1", "pem", "sqlite"):
        assert bad in DENIED_OUTPUT_EXTENSIONS
        assert bad not in DEFAULT_CLIENT_OUTPUT_WRITE_EXTENSIONS


def test_outputs_is_read_write_root() -> None:
    assert "outputs" in READ_WRITE_ROOTS


def test_gate_default_on_and_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE", raising=False)
    assert p.client_output_write_enabled() is True
    gs = p.gate_status()
    assert gs["client_output_write_enabled"] is True
    # independent from scratch/legacy which stay hard-denied on the remote surface
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    assert p.scratch_output_write_enabled() is False
    assert p.legacy_vault_write_enabled() is False
    assert p.client_output_write_enabled() is True


def test_kill_switch_blocks_write_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE", "0")
    assert p.client_output_write_enabled() is False
    assert p.blocked_write_tools() >= p.CLIENT_OUTPUT_WRITE_TOOLS


def test_limits_present() -> None:
    cfg = NasMcpConfig.from_mapping({}, fallback_db={})
    assert cfg.max_client_output_file_bytes == 26_214_400
    assert cfg.max_client_output_zip_members == 200
    assert cfg.max_client_output_zip_uncompressed_bytes == 104_857_600
