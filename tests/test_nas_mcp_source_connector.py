"""N8C-12 — remote NAS MCP read-only source-root connector tools: safety + behavior.

Proves the six ``assistant_source_*`` tools search / list / inspect / bounded-read INDEXED source FILES from a
READ-ONLY DB snapshot (``mode=ro&immutable=1`` + ``query_only=ON``) and never scan/reindex/generate a card/
write; are gated by a default-ON kill switch (``HB_MCP_ASSISTANT_SOURCE_CONNECTOR``) scoped to ONLY these
tools; preserve every existing assistant tool set BY NAME; add no forbidden verb; keep the generic
``hb_root_*`` tools unchanged (not broadened); and keep ``ai_outputs_card_upsert`` the only sanctioned write.
"""

from __future__ import annotations

import hashlib
import inspect
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import (
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
from hb_assistant.nas_mcp.root_tools import hb_root_search
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import source_id_for
from hb_assistant.store.migrator import SQLiteMigrator


class _FakeMcp:
    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


def _seed(db: str, root_key: str, rel_path: str, body: str) -> str:
    sid = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_metadata(source_id,file_ext,size_bytes,mtime_ns,"
                  "content_sha256,extraction_status,fts_rowid,indexed_at) VALUES(?,?,?,1,?,?,NULL,'t')",
                  (sid, "txt", len(body), hashlib.sha256(body.encode()).hexdigest(), "ok"))
        c.execute("INSERT INTO source_intelligence_text(source_id,text_excerpt,excerpt_char_count,"
                  "excerpt_truncated,raw_body_persisted,redaction_applied,updated_at) "
                  "VALUES(?,?,?,0,0,1,'t')", (sid, body, len(body)))
        rowid = c.execute("INSERT INTO source_intelligence_fts(text_excerpt,rel_path,aux) "
                          "VALUES(?,?,NULL)", (body, rel_path)).lastrowid
        c.execute("UPDATE source_intelligence_metadata SET fts_rowid=? WHERE source_id=?", (rowid, sid))
        c.execute("INSERT OR REPLACE INTO source_intelligence_state(state_key,state_value,updated_at) "
                  "VALUES('fts_available','1','t')")
        c.commit()
    return sid


@pytest.fixture()
def mcp_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    (work / "Projects").mkdir(parents=True)
    (work / "Projects" / "contract_A.txt").write_text("payment application for the contract")
    (work / "Projects" / "invoice_B.txt").write_text("invoice payment due")
    sid = _seed(db, "work", "Projects/contract_A.txt", "payment application for the contract")
    _seed(db, "work", "Projects/invoice_B.txt", "invoice payment due")
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="work",
                                                                    path=str(work))])
    monkeypatch.setattr("hb_assistant.obsidian_mcp.config.load_config", lambda: config)
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
    assert "sources_total" in _ok(b, "assistant_source_status", {})
    assert _ok(b, "assistant_source_roots_list", {})["count"] == 1
    assert _ok(b, "assistant_source_files_list", {"source_root_key": "work"})["count"] == 2
    sr = _ok(b, "assistant_source_file_search", {"query": "payment"})
    assert sr["count"] >= 2 and all("source_root_key" in i for i in sr["items"])
    md = _ok(b, "assistant_source_file_metadata", {"source_id": sid})
    assert md["object_type"] == "source_file"
    rd = _ok(b, "assistant_source_file_read", {"source_id": sid, "max_chars": 10})
    assert rd["char_count"] <= 10 and rd["content_source"] == "live_extract"


def test_missing_denied_cleanly(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("assistant_source_file_metadata", {"source_id": "0" * 32})
    assert r["ok"] is False and "source_not_found" in r["error"]


def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE source_intelligence_sources SET deleted=1")
    finally:
        conn.close()


def test_kill_switch_disables_only_source_connector(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    assert b.dispatch("assistant_source_roots_list", {})["ok"] is True  # default ON
    monkeypatch.setenv("HB_MCP_ASSISTANT_SOURCE_CONNECTOR", "0")
    off = b.dispatch("assistant_source_roots_list", {})
    assert off["ok"] is False and off["error"] == "assistant_source_connector_disabled"
    # sibling surfaces stay enabled — the kill switch is scoped to the source connector only.
    assert b.dispatch("assistant_list_research_packets", {})["ok"] is True
    assert b.dispatch("assistant_list_intelligence_projections", {})["ok"] is True
    assert b.dispatch("assistant_list_review_items", {})["ok"] is True


def test_reads_are_not_writes_safe_mode(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert b.dispatch("assistant_source_file_search", {"query": "payment"})["ok"] is True
    w = b.dispatch("ai_outputs_card_upsert", {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False and "safe_mode_active" in w["error"]


def test_no_write_scan_or_action_tool_registered(mcp_env) -> None:
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"])
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    # existing tool sets preserved BY NAME (subset asserts, not just total count).
    for tools in (ASSISTANT_NAV_TOOLS, ASSISTANT_CONTEXT_PACK_TOOLS, ASSISTANT_MEMORY_TOOLS,
                  ASSISTANT_DECISION_MEMORY_TOOLS, ASSISTANT_REVIEW_TOOLS, ASSISTANT_INTELLIGENCE_TOOLS,
                  ASSISTANT_RESEARCH_PACKET_TOOLS, ASSISTANT_SOURCE_CONNECTOR_TOOLS):
        assert set(tools) <= set(assistant)
    assert not [n for n in assistant if any(v in n for v in (
        "extract", "apply", "write", "create", "delete", "persist", "upsert", "close", "reopen",
        "accept", "reject", "defer", "dispose", "build", "send", "remind", "answer", "generate",
        "scan", "reindex", "rebuild"))]
    assert len(ASSISTANT_SOURCE_CONNECTOR_TOOLS) == 6


def test_hb_root_tools_not_broadened(mcp_env) -> None:
    # The generic root browser must stay a shallow, single-directory, name-only search — N8C-12 adds
    # dedicated index-backed tools instead of turning hb_root_* into a recursive/FTS filesystem browser.
    params = set(inspect.signature(hb_root_search).parameters)
    assert params == {"config", "root_key", "query", "relative_path", "limit"}
    assert not (params & {"recursive", "fts", "content", "cursor", "source_root_key"})
    # our new source tools are separate names, never hb_root_*.
    assert not any(n.startswith("hb_root") for n in ASSISTANT_SOURCE_CONNECTOR_TOOLS)


def test_status_reports_source_connector(mcp_env) -> None:
    res = mcp_env["broker"].dispatch("hb_mcp_status", {})["result"]
    assert res["assistant_source_connector_enabled"] is True
    assert set(res["assistant_source_connector_tools"]) == set(ASSISTANT_SOURCE_CONNECTOR_TOOLS)
    assert "ai_outputs_card_upsert" not in set(ASSISTANT_SOURCE_CONNECTOR_TOOLS)
    # source-index search tools stay BLOCKED as raw obsidian tools (not unblocked by N8C-12).
    assert "search_sources" in res["obsidian_tools_blocked"]


def test_live_read_resolves_via_nas_root_injection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression for the deployed Defect-8 failure: load_config() has NO external_sources on the NAS,
    so the broker must inject them from the NAS roots (syn-<key> → mount) or live reads degrade to
    indexed excerpts (root_unavailable). The prior test forced external_sources via load_config, masking
    this — here load_config returns empty and the NAS roots supply the mapping."""
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    work = tmp_path / "work"
    (work / "Projects").mkdir(parents=True)
    (work / "Projects" / "contract_A.txt").write_text("payment application for the contract")
    # Index under the derived key syn-work (roots key "work" → syn-work).
    sid = _seed(db, "syn-work", "Projects/contract_A.txt", "payment application for the contract")
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    # load_config returns the real NAS default: NO external_sources.
    monkeypatch.setattr("hb_assistant.obsidian_mcp.config.load_config", ObsidianMcpConfig)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", vault, "read_write"),
               "work": RootSpec("work", work, "read_only")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=tmp_path / "bk", support_dir=tmp_path / "sup"),
    )
    broker = NasMcpBroker(cfg)
    # roots_list now reflects the injected syn-work root.
    roots = broker.dispatch("assistant_source_roots_list", {})["result"]
    assert any(r["source_root_key"] == "syn-work" for r in roots["roots"])
    # live read resolves instead of falling back to the indexed excerpt.
    rd = broker.dispatch("assistant_source_file_read", {"source_id": sid, "max_chars": 10})["result"]
    assert rd["content_source"] == "live_extract", rd
