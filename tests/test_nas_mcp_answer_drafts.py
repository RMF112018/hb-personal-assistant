"""N8C-14 — remote NAS MCP read-only answer-draft tools: safety + behavior.

Proves the six ``assistant_*_draft*`` tools list / get / inspect / export citation-safe DRAFT artifacts from a
READ-ONLY DB snapshot (``mode=ro&immutable=1`` + ``query_only=ON``) and never write / build / generate an
answer / execute an action; are gated by a default-ON kill switch (``HB_MCP_ASSISTANT_ANSWER_DRAFTS``) scoped
to ONLY these tools; preserve every existing assistant tool set (incl. the N8C-12 source connector) BY NAME;
add no forbidden verb (incl. the substring ``answer``); and keep ``ai_outputs_card_upsert`` the only sanctioned
write.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ASSISTANT_ANSWER_DRAFT_TOOLS,
    ASSISTANT_CONTEXT_PACK_TOOLS,
    ASSISTANT_DECISION_MEMORY_TOOLS,
    ASSISTANT_INTELLIGENCE_TOOLS,
    ASSISTANT_MEMORY_TOOLS,
    ASSISTANT_NAV_TOOLS,
    ASSISTANT_RESEARCH_PACKET_TOOLS,
    ASSISTANT_REVIEW_TOOLS,
    ASSISTANT_SOURCE_CONNECTOR_TOOLS,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.db_tools import _ro_uri
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp import answer_draft_builder as B
from hb_assistant.obsidian_mcp.answer_draft_builder import DraftProviders
from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository
from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
from hb_assistant.store.migrator import SQLiteMigrator


class _FakeMcp:
    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


def _seed_draft(db: str) -> str:
    pr = ResearchPacketRepository(db)
    contract = {"answer_allowed": True, "citation_required": True, "review_labels_required": True,
                "trusted_claims_allowed": True, "candidate_claims_allowed": "with_caveat",
                "must_not_say": [], "unresolved_questions": []}
    acj = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    acd = "d" * 24
    pr.upsert_packet(
        {"packet_id": "PKT", "packet_type": "review_aware_answer_context", "answer_contract_json": acj,
         "status": "built", "created_by": "t", "projection_id": "P", "answer_contract_digest": acd,
         "trusted_count": 1, "citation_count": 1, "item_count": 1, "budget_json": "{}", "scope_json": "{}"},
        [{"packet_item_id": "IT", "packet_id": "PKT", "target_kind": "claim", "target_id": "C",
          "effective_state": "accepted", "inclusion_state": "trusted", "answer_role": "primary_support",
          "title": "T", "summary": "S", "evidence_excerpt": "E", "claim_id": "C", "included": 1}],
        [{"citation_id": "CT", "packet_id": "PKT", "packet_item_id": "IT", "citation_order": 0,
          "citation_type": "claim", "target_kind": "claim", "target_id": "C", "claim_id": "C"}],
        {"packet_receipt_id": "R", "packet_id": "PKT", "builder_version": "v", "input_digest": "i",
         "output_digest": "o", "answer_contract_digest": acd})
    res = B.build_answer_draft(DraftProviders(packet_repo=pr, source_repo=None), AnswerDraftRepository(db),
                               packet_id="PKT", draft_type="review_aware_answer_draft", apply=True)
    return res["draft_id"]


@pytest.fixture()
def mcp_env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    did = _seed_draft(db)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit / "bk", support_dir=audit / "support"),
    )
    return {"broker": NasMcpBroker(cfg), "db": db, "did": did}


def _ok(broker, name, args):
    p = broker.dispatch(name, args)
    assert p["ok"] is True, p
    return p["result"]


def test_tools_return_data(mcp_env) -> None:
    b, did = mcp_env["broker"], mcp_env["did"]
    assert _ok(b, "assistant_list_drafts", {})["count"] == 1
    assert _ok(b, "assistant_get_draft", {"draft_id": did})["draft"]["draft_type"] == \
        "review_aware_answer_draft"
    assert _ok(b, "assistant_get_draft_sections", {"draft_id": did})["count"] >= 1
    assert _ok(b, "assistant_get_draft_citations", {"draft_id": did})["count"] >= 1
    assert _ok(b, "assistant_get_draft_export", {"draft_id": did})["section_count"] >= 1
    assert "total_drafts" in _ok(b, "assistant_get_draft_summary", {})["summary"]


def test_missing_denied_cleanly(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("assistant_get_draft", {"draft_id": "nope"})
    assert r["ok"] is False and "draft_not_found" in r["error"]


def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE assistant_answer_drafts SET status='superseded'")
    finally:
        conn.close()


def test_kill_switch_disables_only_answer_drafts(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    assert b.dispatch("assistant_list_drafts", {})["ok"] is True  # default ON
    monkeypatch.setenv("HB_MCP_ASSISTANT_ANSWER_DRAFTS", "0")
    off = b.dispatch("assistant_list_drafts", {})
    assert off["ok"] is False and off["error"] == "assistant_answer_drafts_disabled"
    # sibling surfaces stay enabled — the kill switch is scoped to the answer-draft tools only.
    assert b.dispatch("assistant_list_research_packets", {})["ok"] is True
    assert b.dispatch("assistant_source_roots_list", {})["ok"] is True
    assert b.dispatch("assistant_list_intelligence_projections", {})["ok"] is True


def test_no_write_build_or_answer_tool_registered(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"], capability_profile="legacy-v12")
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    # existing tool sets preserved BY NAME (incl. the N8C-12 source connector).
    for tools in (ASSISTANT_NAV_TOOLS, ASSISTANT_CONTEXT_PACK_TOOLS, ASSISTANT_MEMORY_TOOLS,
                  ASSISTANT_DECISION_MEMORY_TOOLS, ASSISTANT_REVIEW_TOOLS, ASSISTANT_INTELLIGENCE_TOOLS,
                  ASSISTANT_RESEARCH_PACKET_TOOLS, ASSISTANT_SOURCE_CONNECTOR_TOOLS,
                  ASSISTANT_ANSWER_DRAFT_TOOLS):
        assert set(tools) <= set(assistant)
    # no answer-generation / build / write / action verb in ANY assistant tool name (incl. "answer").
    assert not [n for n in assistant if any(v in n for v in (
        "final_answer", "answer_text", "generated_answer", "operator_approved_answer",
        "authoritative_answer", "send_answer", "generate_answer", "answer", "generate", "build", "apply",
        "write", "create", "delete", "persist", "upsert", "send", "extract", "scan", "reindex", "rebuild"))]
    assert len(ASSISTANT_ANSWER_DRAFT_TOOLS) == 6


def test_status_reports_answer_drafts(mcp_env) -> None:
    res = mcp_env["broker"].dispatch("hb_mcp_status", {})["result"]
    assert res["assistant_answer_drafts_enabled"] is True
    assert set(res["assistant_answer_draft_tools"]) == set(ASSISTANT_ANSWER_DRAFT_TOOLS)
    assert "ai_outputs_card_upsert" not in set(ASSISTANT_ANSWER_DRAFT_TOOLS)


def test_reads_are_not_writes_safe_mode(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert b.dispatch("assistant_list_drafts", {})["ok"] is True
    w = b.dispatch("ai_outputs_card_upsert", {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False and "safe_mode_active" in w["error"]
