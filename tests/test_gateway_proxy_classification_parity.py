"""F-001: hb_assistant_tool_query classification parity across manifest, specs, and MCP annotations."""

from __future__ import annotations

from hb_assistant.nas_mcp.tool_registration import _is_write_tool
from hb_assistant.obsidian_mcp.canonical_tool_specs import (
    CLIENT_BRIDGE_TOOL_SPECS,
    classify_tool,
    tool_spec_public_entry,
)
from hb_assistant.obsidian_mcp.tool_entry_manifest import build_tool_entry


def test_tool_query_classified_as_write_proxy() -> None:
    tc, sc, rw = classify_tool("hb_assistant_tool_query", "client_bridge")
    assert tc == "gateway_proxy"
    assert sc == "broker_gated_proxy"
    assert rw == "write_proxy"


def test_catalog_and_help_remain_read_only() -> None:
    for name in ("hb_assistant_catalog", "hb_assistant_tool_help"):
        tc, sc, rw = classify_tool(name, "client_bridge")
        assert rw == "read_only"
        assert tc == "manifest_lookup"


def test_manifest_entry_matches_classify_tool() -> None:
    entry = tool_spec_public_entry("hb_assistant_tool_query", "client_bridge")
    live = build_tool_entry("hb_assistant_tool_query", "client_bridge")
    assert entry["read_write_class"] == live["read_write_class"] == "write_proxy"
    assert entry["safety_class"] == live["safety_class"] == "broker_gated_proxy"
    assert entry["tool_class"] == "gateway_proxy"


def test_mcp_write_annotation_agrees_with_canonical_spec() -> None:
    assert _is_write_tool("hb_assistant_tool_query") is True
    assert _is_write_tool("hb_assistant_catalog") is False
    spec = CLIENT_BRIDGE_TOOL_SPECS["hb_assistant_tool_query"]
    assert spec.read_write_class == "write_proxy"


def test_client_output_write_tools_classified_as_writes_not_reads() -> None:
    # AI-output split-brain guard: every client-facing output WRITE tool must classify as a write in the
    # canonical spec (which feeds the client manifest / catalog / help), agreeing with the broker gate.
    # Previously assistant_output_* aliases fell through to read_only and were advertised as safe reads.
    from hb_assistant.nas_mcp.profile import CLIENT_OUTPUT_WRITE_TOOLS

    for name in CLIENT_OUTPUT_WRITE_TOOLS:
        _tc, _sc, rw = classify_tool(name)
        assert rw != "read_only", (name, rw)
        assert _is_write_tool(name) is True, name
    for name in ("assistant_output_stage", "assistant_output_commit", "assistant_output_archive_commit"):
        assert classify_tool(name) == ("staged_write", "staged_write_requires_review", "staged_write")