"""N8C-24 — MCP surface: registration, gateway reach, status, write-gate enforcement, invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS, GATEWAY_ALLOWLIST, NasMcpBroker
from hb_assistant.nas_mcp.client_output_tools import ALL_PA_OUTPUT_TOOLS, PA_OUTPUT_WRITE_TOOLS
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from tests.n8c24_helpers import make_env

_WRITE_VERBS = ("write", "upsert", "delete", "create", "persist")
_FINALITY = ("execute", "apply", "generate", "send", "build", "dispatch", "schedule", "repair", "evaluate")


@pytest.fixture()
def surface(tmp_path: Path):
    from mcp.server.fastmcp import FastMCP
    env = make_env(tmp_path)
    mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
    broker = NasMcpBroker(env["config"])
    register_nas_mcp_tools(mcp, broker)
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    return {"env": env, "broker": broker, "tools": tools, "names": set(tools),
            "fn": {n: t.fn for n, t in tools.items()}}


def test_ten_output_tools_registered(surface) -> None:
    assert set(ALL_PA_OUTPUT_TOOLS) <= surface["names"]
    assert len(ALL_PA_OUTPUT_TOOLS) == 10


def test_names_avoid_write_verb_and_finality_substrings() -> None:
    for n in ALL_PA_OUTPUT_TOOLS:
        assert not any(v in n for v in _WRITE_VERBS), n
        assert not any(f in n for f in _FINALITY), n


def test_output_tools_not_in_canonical_78(surface) -> None:
    from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS
    from hb_assistant.nas_mcp.client_output_tools import ALL_PA_OUTPUT_TOOLS
    assert set(ALL_PA_OUTPUT_TOOLS).isdisjoint(set(ALL_ASSISTANT_TOOLS))
    # Canonical assistant tools are present; assistant_output_* aliases may also register.
    assert set(ALL_ASSISTANT_TOOLS) <= set(surface["names"])
    assert len([n for n in surface["names"] if n.startswith("assistant_") and not n.startswith("assistant_output_")]) == len(ALL_ASSISTANT_TOOLS)



def test_output_tools_are_in_gateway_allowlist() -> None:
    assert set(ALL_PA_OUTPUT_TOOLS) <= GATEWAY_ALLOWLIST


def test_status_reports_output_fields(surface) -> None:
    st = surface["broker"].dispatch("hb_mcp_status", {})["result"]
    for k in ("client_output_workspace_enabled", "client_output_write_enabled", "client_output_root_key",
              "client_output_allowed_extensions", "client_output_pending_count", "client_output_committed_count"):
        assert k in st, k


def test_full_loop_via_mcp_and_gateway(surface) -> None:
    fn, out = surface["fn"], surface["env"]["outputs"]
    s = fn["pa_output_stage"](title="Doc", file_type="md", content_mode="markdown_text",
                              content_text="# hi\nbody", destination_state="final")
    r = fn["pa_output_commit"](output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                              idempotency_key=s["idempotency_key"])
    assert r["status"] == "committed" and (out / r["relative_path"]).exists()
    # gateway reach: same stage via hb_assistant_tool_query
    g = fn["hb_assistant_tool_query"]("pa_output_stage", {"title": "G", "file_type": "md",
                                                          "content_mode": "markdown_text", "content_text": "x"})
    assert g["ok"] is True and g["result"]["output_id"]
    # read tools
    assert fn["pa_output_list"]()["count"] >= 1
    assert fn["pa_output_manifest_get"]()["entry_count"] >= 1


def test_gateway_output_write_still_gated(surface, monkeypatch) -> None:
    # With the client-output write gate OFF, a gateway-routed pa_output_stage fails closed at dispatch.
    monkeypatch.setenv("HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE", "0")
    receipt = surface["fn"]["hb_assistant_tool_query"]("pa_output_stage", {"title": "x", "file_type": "md"})
    assert receipt["ok"] is False
    assert "write_tool_blocked_by_profile" in str(receipt.get("error", ""))


def test_write_tools_unregistered_when_gate_off(tmp_path, monkeypatch) -> None:
    from mcp.server.fastmcp import FastMCP
    monkeypatch.setenv("HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE", "0")
    env = make_env(tmp_path)
    mcp = FastMCP("x", json_response=True, stateless_http=True)
    register_nas_mcp_tools(mcp, NasMcpBroker(env["config"]))
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert set(PA_OUTPUT_WRITE_TOOLS).isdisjoint(names)  # writes not registered
    assert "pa_output_list" in names  # reads still registered
