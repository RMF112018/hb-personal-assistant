"""N8C-24 — safety negatives + regression (vault isolation, gateway scope, denied surfaces)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import DENIED_TOOL_NAMES, NasMcpBroker
from hb_assistant.nas_mcp.client_output_workspace import (
    ClientOutputError,
    ClientOutputWorkspaceRepository,
)
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from tests.n8c24_helpers import make_env, stage_and_commit, zip_b64_with_member


@pytest.fixture()
def surface(tmp_path: Path):
    from mcp.server.fastmcp import FastMCP
    env = make_env(tmp_path)
    mcp = FastMCP("x", json_response=True, stateless_http=True)
    broker = NasMcpBroker(env["config"])
    register_nas_mcp_tools(mcp, broker)
    fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    return {"env": env, "broker": broker, "fn": fn, "names": {t.name for t in mcp._tool_manager.list_tools()}}


def test_generated_files_never_touch_the_vault(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ClientOutputWorkspaceRepository(env["config"], env["db"])
    stage_and_commit(repo, file_type="docx", content_mode="docx_from_markdown_or_text", content="# h")
    # everything under outputs; vault untouched
    assert list(env["outputs"].rglob("*.docx"))
    assert not list(env["vault"].rglob("*.docx"))


def test_script_and_exec_extensions_rejected(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ClientOutputWorkspaceRepository(env["config"], env["db"])
    for bad in ("sh", "exe", "py", "js", "ps1"):
        with pytest.raises(Exception):  # noqa: B017
            repo.stage_output_file({"title": "x", "file_type": bad, "content_mode": "text", "content_text": "x"})


def test_zip_traversal_rejected_at_stage(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ClientOutputWorkspaceRepository(env["config"], env["db"])
    with pytest.raises(Exception):  # noqa: B017 — ZipValidationError bubbles up through stage
        repo.stage_output_file({"title": "z", "file_type": "zip", "content_mode": "zip_base64",
                                "content_base64": zip_b64_with_member("../evil.txt")})


def test_unapproved_commit_and_unknown_output_fail_closed(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    repo = ClientOutputWorkspaceRepository(env["config"], env["db"])
    with pytest.raises(ClientOutputError):
        repo.commit_output_file(output_id="OUTPUT-nope", operator_approval_id="x")


def test_safe_mode_denies_output_writes(surface, monkeypatch) -> None:
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    receipt = surface["broker"].dispatch("pa_output_stage", {"title": "x", "file_type": "md"})
    assert receipt["ok"] is False and "safe_mode_active" in str(receipt.get("error", ""))


def test_denied_and_legacy_stay_out_of_gateway(surface) -> None:
    for bad in ("raw_sql", "shell", "exec", "hb_output_write_file", "hb_output_delete", "hb_db_select"):
        receipt = surface["fn"]["hb_assistant_tool_query"](bad, {})
        assert receipt["ok"] is False
        assert receipt["failure_stage"] in ("gateway_allowlist", "broker_policy")
    assert DENIED_TOOL_NAMES.isdisjoint(surface["names"])
