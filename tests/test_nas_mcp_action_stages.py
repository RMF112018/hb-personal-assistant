"""N8C-19 — remote NAS MCP read-only action-stage tools: safety + behavior.

Proves the six ``assistant_*_action_stage*`` tools list / get / inspect / export bounded staged follow-up
CANDIDATES (every item pinned to not_executed / external_system=none / requires_operator_review=1) from a
READ-ONLY DB snapshot (``mode=ro&immutable=1`` + ``query_only=ON``) and never write / build / apply / execute;
are gated by a default-ON kill switch (``HB_MCP_ASSISTANT_ACTION_STAGES``) scoped to ONLY these tools;
preserve every existing assistant tool set BY NAME; add no forbidden verb; and keep ``ai_outputs_card_upsert``
the only sanctioned write."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ASSISTANT_ACTION_STAGE_TOOLS,
    ASSISTANT_ANSWER_DRAFT_TOOLS,
    ASSISTANT_FEEDBACK_TOOLS,
    ASSISTANT_RESEARCH_PACKET_TOOLS,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.db_tools import _ro_uri
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp import action_stage_builder as B
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter
from hb_assistant.store.migrator import SQLiteMigrator


class _FakeMcp:
    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


def _seed(db: str) -> str:
    fs.capture_feedback(FeedbackRepository(db), feedback_type="needs_review",
                        targets=[{"target_kind": "open_loop", "target_id": "OL1", "open_loop_id": "OL1"}],
                        apply=True)
    prov = B.ActionStageProviders(router=WorkflowRouter(db), feedback_repo=FeedbackRepository(db))
    out = B.build_action_stage(prov, ActionStageRepository(db),
                               request_inputs={"workflow_type": "open_loop_triage"}, apply=True)
    return out["stage_id"]


@pytest.fixture()
def mcp_env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    sid = _seed(db)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit / "bk", support_dir=audit / "support"),
    )
    return {"broker": NasMcpBroker(cfg), "db": db, "sid": sid}


def _ok(broker, name, args):
    p = broker.dispatch(name, args)
    assert p["ok"] is True, p
    return p["result"]


def test_tools_return_data(mcp_env) -> None:
    b, sid = mcp_env["broker"], mcp_env["sid"]
    assert _ok(b, "assistant_list_action_stages", {})["count"] == 1
    assert _ok(b, "assistant_get_action_stage", {"stage_id": sid})["stage"]["stage_type"] == \
        "open_loop_actions"
    items = _ok(b, "assistant_get_action_stage_items", {"stage_id": sid})
    assert items["count"] >= 1
    for it in items["items"]:
        assert it["execution_status"] == "not_executed" and it["external_ref"] is None
    assert _ok(b, "assistant_get_action_stage_citations", {"stage_id": sid})["count"] >= 0
    assert "total_stages" in _ok(b, "assistant_get_action_stage_summary", {})["summary"]
    assert _ok(b, "assistant_get_action_stage_export", {"stage_id": sid})["format"] == \
        "action_stage_export_v1"


def test_missing_denied_cleanly(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("assistant_get_action_stage", {"stage_id": "nope"})
    assert r["ok"] is False and "stage_not_found" in r["error"]


def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE assistant_action_stages SET status='superseded'")
    finally:
        conn.close()


def test_kill_switch_disables_only_action_stages(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    assert b.dispatch("assistant_list_action_stages", {})["ok"] is True  # default ON
    monkeypatch.setenv("HB_MCP_ASSISTANT_ACTION_STAGES", "0")
    off = b.dispatch("assistant_list_action_stages", {})
    assert off["ok"] is False and off["error"] == "assistant_action_stages_disabled"
    # sibling surfaces stay enabled — the kill switch is scoped to the action-stage tools only.
    assert b.dispatch("assistant_list_feedback", {})["ok"] is True
    assert b.dispatch("assistant_list_research_packets", {})["ok"] is True


def test_no_write_build_or_execute_tool_registered(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"], capability_profile="legacy-v12")
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    for tools in (ASSISTANT_RESEARCH_PACKET_TOOLS, ASSISTANT_ANSWER_DRAFT_TOOLS, ASSISTANT_FEEDBACK_TOOLS,
                  ASSISTANT_ACTION_STAGE_TOOLS):
        assert set(tools) <= set(assistant)
    assert not [n for n in assistant if any(v in n for v in (
        "execute", "dispatch", "schedule", "remind", "send", "build", "apply", "write", "create", "delete",
        "persist", "upsert", "accept", "reject", "defer", "dispose", "generate", "extract", "scan",
        "reindex", "rebuild"))]
    assert len(ASSISTANT_ACTION_STAGE_TOOLS) == 6


def test_status_reports_action_stages(mcp_env) -> None:
    res = mcp_env["broker"].dispatch("hb_mcp_status", {})["result"]
    assert res["assistant_action_stages_enabled"] is True
    assert set(res["assistant_action_stage_tools"]) == set(ASSISTANT_ACTION_STAGE_TOOLS)
    assert "ai_outputs_card_upsert" not in set(ASSISTANT_ACTION_STAGE_TOOLS)


def test_reads_are_not_writes_safe_mode(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert b.dispatch("assistant_list_action_stages", {})["ok"] is True
    w = b.dispatch("ai_outputs_card_upsert", {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False and "safe_mode_active" in w["error"]
