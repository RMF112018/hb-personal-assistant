"""N8C-23 — MCP surface registration, status fields, safety negatives, and N8C-22 invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.artifact_tools import ALL_PA_TOOLS
from hb_assistant.nas_mcp.broker import ALL_ASSISTANT_TOOLS, DENIED_TOOL_NAMES, NasMcpBroker
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from tests.n8c23_helpers import make_env

_WRITE_VERBS = ("write", "upsert", "delete", "create", "persist")


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


def test_n8c22_invariants_preserved(surface) -> None:
    names = surface["names"]
    assert len([n for n in names if n.startswith("assistant_")]) == 78
    assert set(ALL_PA_TOOLS) <= names
    # pa_ tools are NOT part of the canonical 78 nor the gateway allowlist.
    assert set(ALL_PA_TOOLS).isdisjoint(set(ALL_ASSISTANT_TOOLS))


def test_no_pa_tool_name_trips_write_heuristic(surface) -> None:
    assert [n for n in ALL_PA_TOOLS if any(v in n for v in _WRITE_VERBS)] == []


def test_no_denied_tool_exposed(surface) -> None:
    assert DENIED_TOOL_NAMES.isdisjoint(surface["names"])


def test_gateway_reaches_pa_tools_but_stays_write_gated(surface) -> None:
    # N8C-24 (operator-authorized): the gateway allowlist was expanded to reach the structured-intelligence
    # pa_* surfaces. They are now ROUTED (not rejected as non-allowlisted) — every write still passes the
    # broker gate chain + server-minted approval/idempotency inside the handler. Routing is proven by the
    # receipt shape (ok True/False), NOT a not_allowlisted ValueError.
    for pa in ("pa_artifact_promotion_apply", "pa_session_capture_stage"):
        try:
            receipt = surface["fn"]["hb_assistant_tool_query"](pa, {})
            assert isinstance(receipt, dict) and "ok" in receipt  # routed through broker.dispatch
        except ValueError as exc:  # a bounded validation error from the handler is fine; not_allowlisted is not
            assert "not_an_allowlisted_assistant_tool" not in str(exc)
    # denied + legacy stay rejected at the gateway
    for bad in ("raw_sql", "hb_output_write_file", "hb_db_select"):
        receipt = surface["fn"]["hb_assistant_tool_query"](bad, {})
        assert receipt["ok"] is False
        assert receipt["failure_stage"] in ("gateway_allowlist", "broker_policy")


def test_status_reports_workspace_and_manifest_fields(surface) -> None:
    st = surface["broker"].dispatch("hb_mcp_status", {})["result"]
    for k in ("artifact_workspace_enabled", "artifact_workspace_schema_version",
              "artifact_workspace_pending_proposal_count", "client_tool_manifest_enabled",
              "client_tool_manifest_staleness_state", "client_tool_manifest_review_required"):
        assert k in st, k
    assert st["artifact_workspace_schema_version"] == 112


def test_full_loop_and_manifest_refresh_via_mcp(surface) -> None:
    fn, vault = surface["fn"], surface["env"]["vault"]
    sc = fn["pa_session_capture_stage"](source_client="chatgpt", session_title="Plan",
                                        capture_trigger="document this session",
                                        session_summary="Agreed staged promotion.", selected_excerpts=["x"])
    bd = fn["pa_artifact_proposal_stage"](session_id=sc["session_id"], candidate_artifacts=[
        {"artifact_type": "decision", "title": "Use staging", "domain": "work", "body_markdown": "b", "summary": "s"},
        {"artifact_type": "open_loop", "title": "Name tools", "domain": "work", "body_markdown": "b", "summary": "s"}])
    for pid in bd["proposal_ids"]:
        fn["pa_artifact_proposal_review"](proposal_id=pid, decision="approve", operator_id="bobby")
    val = fn["pa_artifact_promotion_validate"](proposal_bundle_id=bd["proposal_bundle_id"], operator_id="bobby")
    res = fn["pa_artifact_promotion_apply"](promotion_bundle_id=val["promotion_bundle_id"],
                                            operator_approval_id=val["operator_approval_id"],
                                            idempotency_key=val["idempotency_key"])
    assert res["status"] == "promoted" and res["created_count"] == 2
    # future retrieval
    assert fn["pa_canonical_artifact_list"]()["canonical_artifacts"]
    # tool manifest staged refresh -> promote (materializes md+json)
    stg = fn["pa_tool_manifest_refresh_stage"]()
    prom = fn["pa_tool_manifest_refresh_promote"](refresh_proposal_id=stg["refresh_proposal_id"],
                                                  operator_approval_id=stg["operator_approval_id"])
    assert prom["status"] == "promoted"
    assert (vault / "99 System/Manifests/client-tool-operating-manifest.md").exists()
    assert (vault / "99 System/Manifests/client-tool-operating-manifest.json").exists()


def test_manifest_refresh_rejects_forged_approval(surface) -> None:
    fn = surface["fn"]
    stg = fn["pa_tool_manifest_refresh_stage"]()
    with pytest.raises(ValueError, match="operator_approval_mismatch"):
        fn["pa_tool_manifest_refresh_promote"](refresh_proposal_id=stg["refresh_proposal_id"],
                                               operator_approval_id="FORGED")


def test_capture_tool_is_bounded_by_construction(surface) -> None:
    # The staging tool's schema structurally cannot carry a raw transcript — a stronger guarantee than
    # a runtime reject (the repo-level reject is covered in test_n8c23_artifact_workspace).
    params = set(surface["tools"]["pa_session_capture_stage"].parameters["properties"])
    assert params.isdisjoint({"raw_transcript", "full_transcript", "transcript", "messages", "chat_log"})
    assert "session_summary" in params and "selected_excerpts" in params


def test_unapproved_promotion_fails_closed(surface) -> None:
    # a promotion bundle that was never validated cannot be applied
    with pytest.raises(ValueError):
        surface["fn"]["pa_artifact_promotion_apply"](promotion_bundle_id="PROMOB-nope",
                                                     operator_approval_id="x")


def test_vault_path_resolve_refuses_new_top_level(surface) -> None:
    with pytest.raises(ValueError):
        surface["fn"]["pa_vault_path_resolve"](artifact_type="decision", title="t",
                                               operator_override_path="Second Brain/Canonical/x.md")
