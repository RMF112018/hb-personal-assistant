"""N8C-9 — remote NAS MCP read-only review tools: safety + behavior.

Proves the five remote review tools:
  * return bounded, source-linked data from a READ-ONLY DB snapshot (``mode=ro&immutable=1`` +
    ``query_only=ON``, no live-DB fallback) and never write;
  * are gated by a default-ON kill switch (``HB_MCP_ASSISTANT_REVIEW``), independent of the write gates,
    disabling ONLY the review tools;
  * preserve the existing 12 nav + 4 context-pack + 4 memory + 6 decision-memory tools, add NO
    build/apply/disposition/action tool, and keep ``ai_outputs_card_upsert`` the ONLY sanctioned write.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ASSISTANT_CONTEXT_PACK_TOOLS,
    ASSISTANT_DECISION_MEMORY_TOOLS,
    ASSISTANT_MEMORY_TOOLS,
    ASSISTANT_NAV_TOOLS,
    ASSISTANT_REVIEW_TOOLS,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.db_tools import _ro_uri
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp import context_pack_builder as CB
from hb_assistant.obsidian_mcp import decision_memory_extractor as EX
from hb_assistant.obsidian_mcp import review_builder as RB
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator


class _FakeMcp:
    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


@pytest.fixture()
def mcp_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    er, cr, sr = EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db)
    pr, dr = ContextPackRepository(db), DecisionMemoryRepository(db)
    cr.ingest_candidates(
        [ClaimCandidate(claim_type="decision_candidate", claim_text="Keep MCP read-only",
                        evidence_excerpt="ev", confidence=0.8, normalized_subject="mcp",
                        normalized_object="keep read-only"),
         ClaimCandidate(claim_type="commitment", claim_text="I will send the schedule",
                        evidence_excerpt="ev", confidence=0.7, normalized_subject="sched",
                        normalized_object="send schedule")],
        source_id="s1", note_rel_path="Cards/s1.md", extractor_version="rule_based-v1")
    j = er.queue_job(job_type="claim_extraction", source_id="s1")
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"claims": [], "count": 0}),
                    applied_status="stored_only", receipt_metadata={"output_digest": "d1"})
    pack = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=20)),
                                 CB.Providers(er, cr, sr), pr, apply=True)["pack_id"]
    EX.apply_decision_memory(EX.DecisionMemoryProviders(cr, pr, er, sr, MemoryRepository(db)),
                             dr, pack_id=pack, apply=True)
    repo = ReviewRepository(db)
    RB.build_review_queue(RB.ReviewProviders(pr, cr, er, sr, MemoryRepository(db), dr), repo,
                          pack_id=pack, apply=True)
    item = repo.list_review_items(limit=1)[0]
    rid = item["review_item_id"]
    repo.record_disposition(review_item_id=rid, disposition_type="accept", operator_id="bobby")
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit / "bk", support_dir=audit / "support"),
    )
    return {"broker": NasMcpBroker(cfg), "db": db, "review_item_id": rid,
            "target_kind": item["target_kind"], "target_id": item["target_id"]}


def _ok(broker, name, args):
    p = broker.dispatch(name, args)
    assert p["ok"] is True, p
    return p["result"]


def test_tools_return_data(mcp_env) -> None:
    b, rid = mcp_env["broker"], mcp_env["review_item_id"]
    assert _ok(b, "assistant_list_review_items", {})["count"] >= 1
    assert _ok(b, "assistant_get_review_item", {"review_item_id": rid})["review_item"][
        "review_item_id"] == rid
    assert _ok(b, "assistant_get_review_dispositions", {"review_item_id": rid})["count"] >= 1
    eff = _ok(b, "assistant_get_effective_review_state",
              {"target_kind": mcp_env["target_kind"], "target_id": mcp_env["target_id"]})
    assert eff["effective_states"][0]["effective_state"] == "accepted"
    assert "summary" in _ok(b, "assistant_get_review_summary", {})


def test_missing_denied_cleanly(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("assistant_get_review_item", {"review_item_id": "nope"})
    assert r["ok"] is False and "review_item_not_found" in r["error"]


def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE assistant_review_items SET review_state='operator_accepted'")
    finally:
        conn.close()


def test_kill_switch_disables_only_review(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    assert b.dispatch("assistant_list_review_items", {})["ok"] is True  # default ON
    monkeypatch.setenv("HB_MCP_ASSISTANT_REVIEW", "0")
    off = b.dispatch("assistant_list_review_items", {})
    assert off["ok"] is False and off["error"] == "assistant_review_disabled"
    # sibling surfaces stay enabled — the kill switch is scoped to review only
    assert b.dispatch("assistant_list_decisions", {})["ok"] is True


def test_reads_are_not_writes_safe_mode(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert b.dispatch("assistant_list_review_items", {})["ok"] is True  # reads survive safe mode
    w = b.dispatch("ai_outputs_card_upsert", {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False and "safe_mode_active" in w["error"]  # the one write stays gated


def test_no_write_or_action_tool_registered(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"])
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    # nav (12) + context-pack (4) + memory (4) + decision (6) + review (5) preserved; nothing implying
    # a build/apply/disposition/action.
    assert set(ASSISTANT_NAV_TOOLS) <= set(assistant)
    assert set(ASSISTANT_CONTEXT_PACK_TOOLS) <= set(assistant)
    assert set(ASSISTANT_MEMORY_TOOLS) <= set(assistant)
    assert set(ASSISTANT_DECISION_MEMORY_TOOLS) <= set(assistant)
    assert set(ASSISTANT_REVIEW_TOOLS) <= set(assistant)
    assert not [n for n in assistant if any(v in n for v in (
        "extract", "apply", "write", "create", "delete", "persist", "upsert", "close", "reopen",
        "accept", "reject", "defer", "dispose", "build", "send", "remind"))]
    assert len(ASSISTANT_REVIEW_TOOLS) == 5


def test_status_reports_review(mcp_env) -> None:
    res = mcp_env["broker"].dispatch("hb_mcp_status", {})["result"]
    assert res["assistant_review_enabled"] is True
    assert set(res["assistant_review_tools"]) == set(ASSISTANT_REVIEW_TOOLS)
    # ai_outputs_card_upsert remains the only sanctioned write.
    assert "ai_outputs_card_upsert" not in set(ASSISTANT_REVIEW_TOOLS)
