"""N8C-3 — read-only source/card/note navigation service.

Exercises the shared :mod:`hb_assistant.obsidian_mcp.source_navigation` layer that backs BOTH the
local ``GET /api/assistant/*`` API and the remote ``assistant_*`` MCP tools. Everything is read-only;
content is complete/unredacted (Bobby-authorized); structural path fields are always relative; list
responses carry ``count``/``limit``/``truncated``; card->source is ambiguity-aware.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_navigation as nav
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError
from hb_assistant.store.migrator import SQLiteMigrator

REL_A = "docs/alpha.txt"
REL_B = "docs/beta.txt"


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    repo = SourceIndexRepository(db)
    (root / "docs").mkdir(parents=True)
    (root / REL_A).write_text("alpha content unique_token_zzz", encoding="utf-8")
    (root / REL_B).write_text("beta content", encoding="utf-8")
    sid_a = index_source_file(root / REL_A, config.external_sources[0], repo, config)
    sid_b = index_source_file(root / REL_B, config.external_sources[0], repo, config)
    out_a = generate_source_card(repo, config, source_id=sid_a)
    out_b = generate_source_card(repo, config, source_id=sid_b)
    return {"repo": repo, "config": config, "vault": vault, "root": root, "db": db,
            "sid_a": sid_a, "sid_b": sid_b, "card_a": out_a["note_path"], "card_b": out_b["note_path"]}


def _no_absolute_paths(obj, root: str) -> bool:
    """No string value anywhere in the payload is an absolute path under the private root."""
    if isinstance(obj, dict):
        return all(_no_absolute_paths(v, root) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_absolute_paths(v, root) for v in obj)
    if isinstance(obj, str):
        return root not in obj
    return True


# --- search + envelope shape -----------------------------------------------------------
def test_search_sources_bounded_envelope(env) -> None:
    out = nav.search_sources(env["repo"], "unique_token_zzz")
    assert set(out) >= {"sources", "count", "limit", "truncated"}
    assert out["count"] == len(out["sources"]) <= out["limit"]
    assert any(r["source_id"] == env["sid_a"] for r in out["sources"])
    # structural fields are relative, never the private absolute root
    assert _no_absolute_paths(out, str(env["root"]))


def test_search_cards_bounded(env) -> None:
    out = nav.search_cards(env["repo"], "alpha")
    assert set(out) >= {"cards", "count", "limit", "truncated"}
    assert out["count"] <= out["limit"]


def test_limit_is_clamped(env) -> None:
    out = nav.search_sources(env["repo"], "unique_token_zzz", limit=10_000)
    assert out["limit"] == nav.MAX_LIMIT
    out2 = nav.list_stale_cards(env["repo"], limit=-5)
    assert 1 <= out2["limit"] <= nav.MAX_LIMIT


# --- source detail + linkage -----------------------------------------------------------
def test_get_source_detail_relative_only(env) -> None:
    out = nav.get_source(env["repo"], env["sid_a"])
    assert out is not None
    assert out["source"]["rel_path"] == REL_A          # relative
    assert out["source"]["source_root_key"] == "proj"
    assert out["card"]["note_rel_path"] == env["card_a"]
    assert out["is_duplicate"] is False
    assert _no_absolute_paths(out, str(env["root"]))
    assert _no_absolute_paths(out, str(env["vault"]))


def test_get_source_missing_is_none(env) -> None:
    assert nav.get_source(env["repo"], "deadbeef" * 4) is None


def test_get_card_for_source(env) -> None:
    out = nav.get_card_for_source(env["repo"], env["sid_a"])
    assert out["card"]["note_rel_path"] == env["card_a"]
    assert out["source_id"] == env["sid_a"]


def test_card_to_source_unique_and_ambiguous(env) -> None:
    uniq = nav.get_source_for_card(env["repo"], env["card_a"])
    assert uniq["resolution"] == "unique" and uniq["source_id"] == env["sid_a"]
    # two sources claiming one card path -> ambiguous, never arbitrary
    env["repo"].record_generated_note(env["sid_b"], env["card_a"], "generated", "2026-07-05T00:00:00Z")
    amb = nav.get_source_for_card(env["repo"], env["card_a"])
    assert amb["resolution"] == "ambiguous" and amb["source_id"] is None
    assert amb["count"] == 2


def test_card_to_source_none(env) -> None:
    out = nav.get_source_for_card(env["repo"], "Source Notes/Nope/x__000.md")
    assert out["resolution"] == "none" and out["sources"] == []


# --- card state / stale / duplicate / ambiguous ----------------------------------------
def test_card_state_current(env) -> None:
    out = nav.get_card_state(env["repo"], env["config"], env["sid_a"])
    assert out["state"] == "current"
    assert out["card_paths"] == [env["card_a"]]


def test_list_stale_cards(env) -> None:
    env["repo"].mark_generated_notes_stale(env["sid_a"])
    out = nav.list_stale_cards(env["repo"])
    assert any(r["source_id"] == env["sid_a"] for r in out["stale_cards"])
    assert set(out) >= {"stale_cards", "count", "limit", "truncated"}


def test_list_duplicate_cards(env) -> None:
    env["repo"].record_generated_note(env["sid_a"], "Source Notes/Dup/alpha__2.md", "generated",
                                      "2026-07-05T00:00:00Z")
    out = nav.list_duplicate_cards(env["repo"])
    hit = [d for d in out["duplicate_cards"] if d["source_id"] == env["sid_a"]]
    assert hit and hit[0]["card_count"] == 2


def test_list_ambiguous_card_links(env) -> None:
    env["repo"].record_generated_note(env["sid_b"], env["card_a"], "generated", "2026-07-05T00:00:00Z")
    out = nav.list_ambiguous_card_links(env["repo"])
    hit = [a for a in out["ambiguous_card_links"] if a["note_rel_path"] == env["card_a"]]
    assert hit and set(hit[0]["source_ids"]) == {env["sid_a"], env["sid_b"]}


# --- recent changes + related ----------------------------------------------------------
def test_recent_changes_shape_and_order(env) -> None:
    # Insert two events directly (indexer queue rows) to prove newest-first + bounding.
    with sqlite3.connect(env["db"]) as c:
        c.execute("INSERT INTO source_intelligence_events (event_id, event_type, status, created_at) "
                  "VALUES ('e1','created','done','2026-07-01T00:00:00Z')")
        c.execute("INSERT INTO source_intelligence_events (event_id, event_type, status, created_at) "
                  "VALUES ('e2','modified','done','2026-07-05T00:00:00Z')")
    out = nav.recent_changes(env["repo"], limit=1)
    assert set(out) >= {"changes", "count", "limit", "truncated"}
    assert out["changes"][0]["event_id"] == "e2"   # newest first
    assert out["truncated"] is True                # more than the limit existed


def test_get_related_sources(env) -> None:
    env["repo"].record_relationships(env["sid_a"], [
        {"dst_kind": "source", "dst_ref": env["sid_b"], "relation": "mentions", "confidence": 0.9}])
    out = nav.get_related_sources(env["repo"], env["sid_a"])
    assert out["count"] == 1
    assert out["related"][0]["dst_ref"] == env["sid_b"]


# --- bounded/complete vault-note read + path safety ------------------------------------
def test_get_vault_note_complete_content(env) -> None:
    # The generated source card is a real vault note; read it back in full.
    out = nav.get_vault_note(env["config"], env["card_a"])
    assert out["path"] == env["card_a"]
    assert out["file_type"] == "md"
    assert out["content"]                                   # non-empty, complete
    assert out["metadata"]["truncated"] is False
    assert "note_type" in out


def test_get_vault_note_rejects_traversal_absolute_nul_hidden(env) -> None:
    for bad in ["../secret.txt", "/etc/passwd", ".obsidian/config", ".hidden/x.md"]:
        with pytest.raises(ObsidianMcpToolError):
            nav.get_vault_note(env["config"], bad)
    with pytest.raises(ObsidianMcpToolError):
        nav.get_vault_note(env["config"], "a\x00b.md")


def test_get_vault_note_rejects_symlink_escape(env, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET", encoding="utf-8")
    link = env["vault"] / "escape.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not permitted on this platform")
    with pytest.raises(ObsidianMcpToolError):
        nav.get_vault_note(env["config"], "escape.md")


# --- read-only connection threading ----------------------------------------------------
def test_conn_threading_read_only(env) -> None:
    conn = sqlite3.connect(env["db"])
    conn.execute("PRAGMA query_only=ON")
    try:
        out = nav.search_sources(env["repo"], "unique_token_zzz", conn=conn)
        assert any(r["source_id"] == env["sid_a"] for r in out["sources"])
        state = nav.get_card_state(env["repo"], env["config"], env["sid_a"], conn=conn)
        assert state["state"] == "current"
    finally:
        conn.close()
