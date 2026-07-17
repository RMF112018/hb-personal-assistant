"""N8C-3 — remote NAS MCP ``assistant_*`` navigation tools: safety + behavior.

MCP-side safety proof ONLY (kept separate from the API proof, clarification #4). Proves the remote
read/navigation tools:
  * return complete, unredacted content from a READ-ONLY DB snapshot (``query_only``, no live-DB
    fallback) — the deliberate, operator-authorized full-content posture;
  * never write, are allowed in safe mode, and keep ``ai_outputs_card_upsert`` the ONLY write;
  * leave the denied raw-SQL/shell/fs tools denied and the obsidian tool count (56) unchanged;
  * are gated by a default-ON kill switch (``HB_MCP_ASSISTANT_NAV``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import ASSISTANT_NAV_TOOLS, NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.db_tools import _ro_uri
from hb_assistant.nas_mcp.obsidian_adapter import list_nas_obsidian_tool_names
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

REL_A = "docs/alpha.txt"


@pytest.fixture()
def mcp_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    pacfg = tmp_path / "c.yml"
    pacfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(pacfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / REL_A).write_text("alpha body findme_qqq with an email a@b.com and 555-123-4567", encoding="utf-8")
    ob = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    repo = SourceIndexRepository(db)
    sid = index_source_file(root / REL_A, ob.external_sources[0], repo, ob)
    card = generate_source_card(repo, ob, source_id=sid)["note_path"]
    # Checkpoint the WAL so the immutable read-only snapshot sees the committed rows.
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    audit = tmp_path / "audit"
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(audit / "support"))
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=audit / "bk", support_dir=audit / "support"),
    )
    return {"broker": NasMcpBroker(cfg), "cfg": cfg, "sid": sid, "card": card, "db": db, "vault": vault}


# --- behavior: reads return real, complete content ------------------------------------
def test_assistant_search_and_get_source(mcp_env) -> None:
    b, sid = mcp_env["broker"], mcp_env["sid"]
    r = b.dispatch("assistant_search_sources", {"query": "findme_qqq"})
    assert r["ok"] is True
    assert any(s["source_id"] == sid for s in r["result"]["sources"])
    got = b.dispatch("assistant_get_source", {"source_id": sid})
    assert got["ok"] is True
    assert got["result"]["source"]["rel_path"] == REL_A
    assert got["result"]["card"]["note_rel_path"] == mcp_env["card"]


def test_assistant_vault_note_complete_and_unredacted(mcp_env) -> None:
    # Read the raw external source file's twin card note; then read the card fully. Complete content,
    # no PII redaction is applied by the nav layer (Bobby-authorized).
    b = mcp_env["broker"]
    r = b.dispatch("assistant_get_vault_note", {"note_rel_path": mcp_env["card"]})
    assert r["ok"] is True
    assert r["result"]["file_type"] == "md"
    assert r["result"]["content"]
    assert r["result"]["metadata"]["truncated"] is False


def test_assistant_card_state_and_recent_changes(mcp_env) -> None:
    b, sid = mcp_env["broker"], mcp_env["sid"]
    st = b.dispatch("assistant_get_card_state", {"source_id": sid})
    assert st["ok"] is True and st["result"]["state"] == "current"
    rc = b.dispatch("assistant_recent_changes", {"limit": 5})
    assert rc["ok"] is True
    assert {"changes", "count", "limit", "truncated"} <= set(rc["result"])


def test_assistant_get_source_missing_denied_cleanly(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("assistant_get_source", {"source_id": "0" * 32})
    assert r["ok"] is False and "source_not_found" in r["error"]


# --- safety: read-only snapshot, no live-DB fallback ----------------------------------
def test_snapshot_is_read_only(mcp_env) -> None:
    conn = sqlite3.connect(_ro_uri(mcp_env["db"]), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE hack(x)")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE source_intelligence_sources SET deleted=1")
    finally:
        conn.close()


def test_assistant_reads_are_not_writes(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    # reads still work in safe mode
    assert b.dispatch("assistant_recent_changes", {})["ok"] is True
    assert b.dispatch("assistant_search_sources", {"query": "x"})["ok"] is True
    # the single write remains denied in safe mode (still the only write path)
    w = b.dispatch("ai_outputs_card_upsert", {"title": "t", "body_markdown": "b"})
    assert w["ok"] is False and "safe_mode_active" in w["error"]


def test_denied_tools_stay_denied(mcp_env) -> None:
    b = mcp_env["broker"]
    for t in ("raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"):
        r = b.dispatch(t, {})
        assert r["ok"] is False and r["error"] == "action_denied_by_policy"


def test_kill_switch(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    b = mcp_env["broker"]
    assert b.dispatch("assistant_recent_changes", {})["ok"] is True   # default ON
    monkeypatch.setenv("HB_MCP_ASSISTANT_NAV", "0")
    off = b.dispatch("assistant_recent_changes", {})
    assert off["ok"] is False and off["error"] == "assistant_nav_disabled"


# --- surface invariants ----------------------------------------------------------------
def test_obsidian_tool_count_unchanged(mcp_env) -> None:
    assert len(list_nas_obsidian_tool_names()) == 56       # assistant_* are NOT obsidian tools
    assert len(ASSISTANT_NAV_TOOLS) == 12


def test_mcp_status_reports_assistant(mcp_env) -> None:
    r = mcp_env["broker"].dispatch("hb_mcp_status", {})
    res = r["result"]
    assert res["assistant_nav_enabled"] is True
    assert set(res["assistant_nav_tools"]) == set(ASSISTANT_NAV_TOOLS)


class _FakeMcp:
    """Minimal FastMCP stand-in that records registered tool names."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.names.append(name or fn.__name__)
            return fn
        return deco


def test_registration_adds_12_assistant_tools_when_enabled(mcp_env) -> None:
    from hb_assistant.nas_mcp.broker import ASSISTANT_CONTEXT_PACK_TOOLS

    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"], capability_profile="legacy-v12")
    assistant = [n for n in mcp.names if n.startswith("assistant_")]
    # The 12 N8C-3 nav tools are preserved (clarification #3); the N8C-6 read-only context-pack
    # tools are additive (both gates default-ON).
    assert set(ASSISTANT_NAV_TOOLS) <= set(assistant)
    nav = [n for n in assistant if n in ASSISTANT_NAV_TOOLS]
    assert set(nav) == set(ASSISTANT_NAV_TOOLS)
    assert set(ASSISTANT_CONTEXT_PACK_TOOLS) <= set(assistant)
    # existing hb_* status/read tools are still registered (not renamed/removed)
    assert "hb_data_freshness" in mcp.names and "ai_outputs_card_upsert" in mcp.names


def test_registration_omits_nav_tools_when_disabled(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_MCP_ASSISTANT_NAV", "0")
    mcp = _FakeMcp()
    register_nas_mcp_tools(mcp, mcp_env["broker"], capability_profile="legacy-v12")
    assert not [n for n in mcp.names if n in ASSISTANT_NAV_TOOLS]  # nav kill switch honored
    assert "hb_data_freshness" in mcp.names        # unrelated tools unaffected
