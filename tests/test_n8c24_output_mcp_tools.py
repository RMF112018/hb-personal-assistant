"""N8C-24 — MCP surface: registration, gateway reach, status, write-gate enforcement, invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS, GATEWAY_ALLOWLIST, NasMcpBroker
from hb_assistant.nas_mcp.client_output_tools import (
    ALL_PA_OUTPUT_TOOLS,
    ASSISTANT_OUTPUT_ALIASES,
    PA_OUTPUT_WRITE_TOOLS,
)
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from tests.n8c24_helpers import good_zip_b64, make_env

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
    # Client-facing aliases share gateway reach with pa_output_*.
    assert set(ASSISTANT_OUTPUT_ALIASES) <= GATEWAY_ALLOWLIST
    assert len(ASSISTANT_OUTPUT_ALIASES) == 10


def test_assistant_output_aliases_registered(surface) -> None:
    assert set(ASSISTANT_OUTPUT_ALIASES) <= surface["names"]


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
    # Write aliases follow the same gate; read aliases remain.
    assert "assistant_output_stage" not in names
    assert "assistant_output_commit" not in names
    assert "assistant_output_archive_commit" not in names
    assert "assistant_output_list" in names
    assert "assistant_output_metadata" in names


def test_assistant_output_aliases_broker_callable_parity(surface) -> None:
    """All 10 assistant_output_* aliases must dispatch through the broker (not tool_not_registered).

    Regression: a broad ``startswith('assistant_')`` catch-all previously swallowed aliases
    before the client-output handler, so tools/list advertised them but tools/call failed.
    """
    broker = surface["broker"]
    fn = surface["fn"]
    out = surface["env"]["outputs"]

    # --- broker.dispatch path (mirrors FastMCP _assistant_result) ---
    for alias, pa in zip(ASSISTANT_OUTPUT_ALIASES, ALL_PA_OUTPUT_TOOLS, strict=True):
        assert alias == "assistant_output_" + pa[len("pa_output_") :]

    # Stage via alias
    stage = broker.dispatch(
        "assistant_output_stage",
        {
            "title": "AliasDoc",
            "file_type": "md",
            "content_mode": "markdown_text",
            "content_text": "# alias stage\n",
            "destination_state": "pending",
            "source_client": "alias-test",
        },
    )
    assert stage["ok"] is True, stage
    assert stage["result"]["output_id"]
    assert stage["result"]["operator_approval_id"]
    oid = stage["result"]["output_id"]
    approval = stage["result"]["operator_approval_id"]
    idem = stage["result"]["idempotency_key"]

    # List / metadata / read_excerpt via aliases (pre-commit: staged still listable)
    listed = broker.dispatch("assistant_output_list", {"limit": 20})
    assert listed["ok"] is True, listed
    assert listed["result"]["count"] >= 1

    meta = broker.dispatch("assistant_output_metadata", {"output_id": oid})
    assert meta["ok"] is True, meta
    assert meta["result"]["output_id"] == oid

    # Commit via alias
    commit = broker.dispatch(
        "assistant_output_commit",
        {"output_id": oid, "operator_approval_id": approval, "idempotency_key": idem},
    )
    assert commit["ok"] is True, commit
    assert commit["result"]["status"] == "committed"
    assert (out / commit["result"]["relative_path"]).exists()

    # Read excerpt after commit
    excerpt = broker.dispatch("assistant_output_read_excerpt", {"output_id": oid, "max_chars": 200})
    assert excerpt["ok"] is True, excerpt

    # Manifest
    manifest = broker.dispatch("assistant_output_manifest_get", {})
    assert manifest["ok"] is True, manifest
    assert manifest["result"]["entry_count"] >= 1

    # Receipt (from commit)
    receipt_id = commit["result"].get("receipt_id") or meta["result"].get("receipt_id")
    if not receipt_id:
        meta2 = broker.dispatch("assistant_output_metadata", {"output_id": oid})
        receipt_id = (meta2.get("result") or {}).get("receipt_id")
    if receipt_id:
        receipt = broker.dispatch("assistant_output_receipt_get", {"receipt_id": receipt_id})
        assert receipt["ok"] is True, receipt

    # Zip stage + inspect via aliases
    z_stage = broker.dispatch(
        "assistant_output_stage",
        {
            "title": "AliasZip",
            "file_type": "zip",
            "content_mode": "zip_base64",
            "content_base64": good_zip_b64(),
            "content_text": good_zip_b64(),
            "destination_state": "pending",
        },
    )
    # content_mode may require zip_base64 or base64_binary depending on renderer
    if not z_stage.get("ok"):
        z_stage = broker.dispatch(
            "assistant_output_stage",
            {
                "title": "AliasZip",
                "file_type": "zip",
                "content_mode": "base64_binary",
                "content_base64": good_zip_b64(),
                "content_text": good_zip_b64(),
            },
        )
    assert z_stage["ok"] is True, z_stage
    z_oid = z_stage["result"]["output_id"]
    z_appr = z_stage["result"]["operator_approval_id"]
    z_idem = z_stage["result"]["idempotency_key"]
    z_insp = broker.dispatch("assistant_output_zip_inspect", {"output_id": z_oid})
    assert z_insp["ok"] is True, z_insp
    z_commit = broker.dispatch(
        "assistant_output_commit",
        {"output_id": z_oid, "operator_approval_id": z_appr, "idempotency_key": z_idem},
    )
    assert z_commit["ok"] is True, z_commit
    assert z_commit["result"]["status"] == "committed"

    # Archive plan + commit via aliases for both outputs
    for target_oid in (oid, z_oid):
        plan = broker.dispatch("assistant_output_archive_plan", {"output_id": target_oid})
        assert plan["ok"] is True, plan
        arch_appr = plan["result"]["operator_approval_id"]
        arch = broker.dispatch(
            "assistant_output_archive_commit",
            {"output_id": target_oid, "operator_approval_id": arch_appr},
        )
        assert arch["ok"] is True, arch
        assert arch["result"]["status"] == "archived"

    # FastMCP direct fn path (same as tools/call registration) for write aliases
    s2 = fn["assistant_output_stage"](
        title="AliasFn",
        file_type="md",
        content_mode="markdown_text",
        content_text="# via fn\n",
    )
    assert s2["output_id"]
    c2 = fn["assistant_output_commit"](
        output_id=s2["output_id"],
        operator_approval_id=s2["operator_approval_id"],
        idempotency_key=s2["idempotency_key"],
    )
    assert c2["status"] == "committed"

    # Gateway-routed alias write
    g = fn["hb_assistant_tool_query"](
        "assistant_output_stage",
        {"title": "AliasGW", "file_type": "md", "content_mode": "markdown_text", "content_text": "gw"},
    )
    assert g["ok"] is True and g["result"]["output_id"]

    # pa_output_* still works (compatibility)
    s3 = broker.dispatch(
        "pa_output_stage",
        {"title": "PaStill", "file_type": "md", "content_mode": "markdown_text", "content_text": "pa"},
    )
    assert s3["ok"] is True and s3["result"]["output_id"]


def test_assistant_output_alias_gateway_write_still_gated(surface, monkeypatch) -> None:
    monkeypatch.setenv("HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE", "0")
    receipt = surface["fn"]["hb_assistant_tool_query"](
        "assistant_output_stage", {"title": "x", "file_type": "md"}
    )
    assert receipt["ok"] is False
    assert "write_tool_blocked_by_profile" in str(receipt.get("error", ""))


def test_broker_dispatch_rejects_unknown_assistant_output_suffix(surface) -> None:
    # Unknown alias-shaped name must not fall through to nav and claim success.
    receipt = surface["broker"].dispatch("assistant_output_not_a_real_tool", {})
    assert receipt["ok"] is False
    err = str(receipt.get("error", ""))
    assert "tool_not_registered" in err or "unknown" in err.lower() or "not" in err.lower()
