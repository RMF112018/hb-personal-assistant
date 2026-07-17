"""N8C-7 — remote NAS MCP read-only memory tools: safety + behavior.

Proves the four remote memory tools:
  * return bounded, source-linked data from a READ-ONLY DB snapshot (``mode=ro&immutable=1`` +
    ``query_only=ON``, no live-DB fallback) and never write;
  * are gated by a default-ON kill switch (``HB_MCP_ASSISTANT_MEMORY``), independent of the write gates;
  * preserve the existing 12 nav tools + 4 context-pack tools, add NO compile/apply/write tool, and
    keep ``ai_outputs_card_upsert`` the ONLY sanctioned remote write.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
    ASSISTANT_CONTEXT_PACK_TOOLS,
    ASSISTANT_MEMORY_TOOLS,
    ASSISTANT_NAV_TOOLS,
    NasMcpBroker,
)
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.db_tools import _ro_uri
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp import context_pack_builder as B
from hb_assistant.obsidian_mcp import memory_compiler as MC
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
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
    cr.ingest_candidates(
        [ClaimCandidate(claim_type="fact", claim_text="Tropical uses Procore",
                        evidence_excerpt="ev", confidence=0.8,
                        normalized_subject="Tropical Waters", normalized_object="Procore")],
        source_id="s1", note_rel_path="Cards/s1.md", extractor_version="rule_based-v1")
    j = er.queue_job(job_type="claim_extraction", source_id="s1")
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"claims": [], "count": 0}),
                    applied_status="stored_only", receipt_metadata={"output_digest": "d1"})
    pr, mr = ContextPackRepository(db), MemoryRepository(db)
    res = B.build_context_pack(B.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=10)),
                               B.Providers(er, cr, sr), pr, apply=True)
    MC.apply_memory_compilation(MC.MemoryProviders(cr, pr, er, sr), mr,
                                pack_id=res["pack_id"], apply=True)
    node_id = mr.list_nodes()[0]["node_id"]
    # Checkpoint the WAL so the immutable read-only snapshot sees the committed rows.
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
    return {"broker": NasMcpBroker(cfg), "db": db, "node_id": node_id}


def _ok(broker, name, args):
    p = broker.dispatch(name, args)
    assert p["ok"] is True, p
    return p["result"]


def test_memory_tools_return_data(mcp_env) -> None:
    b, nid = mcp_env["broker"], mcp_env["node_id"]
    assert _ok(b, "assistant_list_memory_nodes", {})["count"] >= 1
    assert _ok(b, "assistant_get_memory_node", {"node_id": nid})["memory_node"]["node_id"] == nid
    assert _ok(b, "assistant_get_memory_mentions", {"node_id": nid})["count"] >= 1
    assert "compilations" in _ok(b, "assistant_get_memory_compilations", {"node_id": nid})


def test_missing_node_denied_cleanly(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("assistant_get_memory_node", {"node_id": "nope"})
    assert r["ok"] is False and "memory_node_not_found" in r["error"]


def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE assistant_memory_nodes SET status='stale'")
    finally:
        conn.close()


def test_kill_switch(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    assert b.dispatch("assistant_list_memory_nodes", {})["ok"] is True   # default ON
    monkeypatch.setenv("HB_MCP_ASSISTANT_MEMORY", "0")
    off = b.dispatch("assistant_list_memory_nodes", {})
    assert off["ok"] is False and off["error"] == "assistant_memory_disabled"


def test_reads_are_not_writes_safe_mode(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert b.dispatch("assistant_list_memory_nodes", {})["ok"] is True  # reads survive safe mode
    w = b.dispatch("ai_outputs_card_upsert", {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False and "safe_mode_active" in w["error"]  # the one write stays gated


def test_no_memory_write_tool_registered(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"], capability_profile="legacy-v12")
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    # nav (12) + context-pack (4) + memory (4) preserved; nothing implying a write/compile/apply.
    assert set(ASSISTANT_NAV_TOOLS) <= set(assistant)
    assert set(ASSISTANT_CONTEXT_PACK_TOOLS) <= set(assistant)
    assert set(ASSISTANT_MEMORY_TOOLS) <= set(assistant)
    assert not [n for n in assistant if any(v in n for v in ("build", "apply", "write", "create",
                                                             "delete", "persist", "upsert", "compile"))]
    assert len(ASSISTANT_MEMORY_TOOLS) == 4


def test_status_reports_memory(mcp_env) -> None:
    res = mcp_env["broker"].dispatch("hb_mcp_status", {})["result"]
    assert res["assistant_memory_enabled"] is True
    assert set(res["assistant_memory_tools"]) == set(ASSISTANT_MEMORY_TOOLS)
