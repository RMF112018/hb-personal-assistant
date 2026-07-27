"""N8C-18 — remote NAS MCP read-only feedback tools: safety + behavior.

Proves the six ``assistant_*_feedback*`` tools list / get / inspect / export bounded operator feedback +
ADVISORY review-loop recommendations from a READ-ONLY DB snapshot (``mode=ro&immutable=1`` + ``query_only=ON``)
and never write / build / apply / dispose / execute; are gated by a default-ON kill switch
(``HB_MCP_ASSISTANT_FEEDBACK``) scoped to ONLY these tools; preserve every existing assistant tool set BY NAME;
add no forbidden verb; and keep ``ai_outputs_card_upsert`` the only sanctioned write."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ASSISTANT_ANSWER_DRAFT_TOOLS,
    ASSISTANT_FEEDBACK_TOOLS,
    ASSISTANT_INTELLIGENCE_TOOLS,
    ASSISTANT_RESEARCH_PACKET_TOOLS,
    ASSISTANT_SOURCE_CONNECTOR_TOOLS,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.db_tools import _ro_uri
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
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
    out = fs.capture_feedback(
        FeedbackRepository(db), feedback_type="wrong_source",
        targets=[{"target_kind": "citation", "target_id": "C1", "source_ref": "sr-1"}],
        note="check", created_by="test", apply=True)
    return out["feedback"]["feedback_id"]


@pytest.fixture()
def mcp_env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    fid = _seed(db)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit / "bk", support_dir=audit / "support"),
    )
    return {"broker": NasMcpBroker(cfg), "db": db, "fid": fid}


def _ok(broker, name, args):
    p = broker.dispatch(name, args)
    assert p["ok"] is True, p
    return p["result"]


def test_tools_return_data(mcp_env) -> None:
    b, fid = mcp_env["broker"], mcp_env["fid"]
    assert _ok(b, "assistant_list_feedback", {})["count"] == 1
    assert _ok(b, "assistant_get_feedback", {"feedback_id": fid})["feedback"]["feedback_type"] == \
        "wrong_source"
    assert _ok(b, "assistant_get_feedback_targets", {"feedback_id": fid})["count"] >= 1
    recs = _ok(b, "assistant_get_feedback_recommendations", {})
    assert recs["count"] >= 1
    assert all(r["review_policy"] == "advisory_review_loop" for r in recs["recommendations"])
    assert "total_feedback" in _ok(b, "assistant_get_feedback_summary", {})["summary"]
    assert _ok(b, "assistant_get_feedback_export", {"feedback_id": fid})["format"] == "feedback_export_v1"


def test_missing_denied_cleanly(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("assistant_get_feedback", {"feedback_id": "nope"})
    assert r["ok"] is False and "feedback_not_found" in r["error"]


def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE assistant_feedback_records SET status='resolved'")
    finally:
        conn.close()


def test_kill_switch_disables_only_feedback(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    assert b.dispatch("assistant_list_feedback", {})["ok"] is True  # default ON
    monkeypatch.setenv("HB_MCP_ASSISTANT_FEEDBACK", "0")
    off = b.dispatch("assistant_list_feedback", {})
    assert off["ok"] is False and off["error"] == "assistant_feedback_disabled"
    # sibling surfaces stay enabled — the kill switch is scoped to the feedback tools only.
    assert b.dispatch("assistant_list_research_packets", {})["ok"] is True
    assert b.dispatch("assistant_source_roots_list", {})["ok"] is True


def test_no_write_build_or_disposition_tool_registered(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"], capability_profile="legacy-v12")
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    for tools in (ASSISTANT_RESEARCH_PACKET_TOOLS, ASSISTANT_SOURCE_CONNECTOR_TOOLS,
                  ASSISTANT_ANSWER_DRAFT_TOOLS, ASSISTANT_INTELLIGENCE_TOOLS, ASSISTANT_FEEDBACK_TOOLS):
        assert set(tools) <= set(assistant)
    # No write / build / apply / disposition / execution verb in ANY assistant tool name.
    assert not [n for n in assistant if any(v in n for v in (
        "accept", "reject", "defer", "dispose", "generate", "build", "apply", "write", "create",
        "delete", "persist", "upsert", "send", "extract", "scan", "reindex", "rebuild", "execute",
        "schedule", "remind"))]
    assert len(ASSISTANT_FEEDBACK_TOOLS) == 6


def test_status_reports_feedback(mcp_env) -> None:
    res = mcp_env["broker"].dispatch("hb_mcp_status", {})["result"]
    assert res["assistant_feedback_enabled"] is True
    assert set(res["assistant_feedback_tools"]) == set(ASSISTANT_FEEDBACK_TOOLS)
    assert "ai_outputs_card_upsert" not in set(ASSISTANT_FEEDBACK_TOOLS)


def test_reads_are_not_writes_safe_mode(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert b.dispatch("assistant_list_feedback", {})["ok"] is True
    w = b.dispatch("ai_outputs_card_upsert", {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False and "safe_mode_active" in w["error"]
