"""N8C-24 — Client Tool Operating Manifest integration (output tools classified + surfaced)."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.nas_mcp.artifact_tools import current_tool_names
from hb_assistant.nas_mcp.client_output_tools import ALL_PA_OUTPUT_TOOLS
from hb_assistant.obsidian_mcp.client_tool_manifest import classify_tool
from tests.n8c24_helpers import make_env


def test_output_tools_appear_in_live_tool_surface(tmp_path: Path) -> None:
    config = make_env(tmp_path)["config"]
    config.capability_profile = "legacy-v12"
    names = current_tool_names(config)
    assert set(ALL_PA_OUTPUT_TOOLS) <= names


def test_output_tools_classified_as_output_family_reads_or_staged() -> None:
    # legacy hb_output_* classify as legacy_low_level; the new pa_output_* are staged_write/read_only.
    assert classify_tool("hb_output_write_file", None)[0] == "legacy_low_level"
    tc, sc, rw = classify_tool("pa_output_stage", None)
    assert rw in ("staged_write", "read_only")
    assert classify_tool("pa_output_list", None)[2] == "read_only"


def test_write_tools_gated_out_of_surface_when_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE", "0")
    config = make_env(tmp_path)["config"]
    config.capability_profile = "legacy-v12"
    names = current_tool_names(config)
    assert "pa_output_commit" not in names
    assert "pa_output_list" in names
