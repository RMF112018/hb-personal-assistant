"""Phase 5 — domain-routed Source Notes: routing, safe filenames, idempotency, guard coverage.

Temp vaults + synthetic source details only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import (
    index_source_file,
    is_source_notes_path,
    scan_vault_notes,
)
from hb_assistant.obsidian_mcp.source_notes import (
    _card_rel_path,
    _domain_for,
    _safe_basename,
    generate_source_card,
)
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError
from hb_assistant.store.migrator import SQLiteMigrator

_CFG = ObsidianMcpConfig()


def _detail(source_id: str, root_key: str, rel_path: str | None) -> dict:
    return {"source_id": source_id, "source_root_key": root_key, "rel_path": rel_path}


# ----- domain derivation (single source of truth) --------------------------------------------
def test_domain_for_routing() -> None:
    for key in ("hb-onedrive", "syn-work", "procore", "sharepoint", "onedrive-x"):
        assert _domain_for({"source_root_key": key}) == "work", key
    for key in ("syn-home", "home-personal"):
        assert _domain_for({"source_root_key": key}) == "home", key
    for key in ("", "misc", "unknown-root"):
        assert _domain_for({"source_root_key": key}) == "shared", key


def test_card_rel_path_routes_by_domain() -> None:
    work = _card_rel_path(_CFG, _detail("abc123def456ghi", "syn-work", "25-244/Change Orders/PCCO 014.pdf"))
    assert work.startswith("Source Notes/Work/") and work.endswith("__abc123def456.md")
    assert "PCCO 014.pdf" in work
    # No source directory replication and no full path leakage in the filename.
    assert "Change Orders" not in work and "25-244" not in work
    assert _card_rel_path(_CFG, _detail("x" * 32, "syn-home", "Budget/2026.xlsx")).startswith("Source Notes/Home/")
    assert _card_rel_path(_CFG, _detail("y" * 32, "weird", "a/b.pdf")).startswith("Source Notes/Shared/")


def test_card_rel_path_link_source() -> None:
    p = _card_rel_path(_CFG, {"source_id": "z" * 32, "source_kind": "email", "domain_ref_id": "msg-1"})
    assert p.startswith("Source Notes/Shared/") and p.endswith("__zzzzzzzzzzzz.md")


# ----- safe basename guarantees (req #2) -----------------------------------------------------
def test_safe_basename_guarantees() -> None:
    # path separators / directories dropped
    assert "/" not in _safe_basename({"rel_path": "a/b/c.pdf"})
    assert "\\" not in _safe_basename({"rel_path": "a\\b\\c.pdf"})
    # parent traversal neutralized
    b = _safe_basename({"rel_path": "../../etc/passwd"})
    assert ".." not in b and "/" not in b
    # absolute path fragment → only basename, no leading slash
    assert not _safe_basename({"rel_path": "/etc/hosts"}).startswith("/")
    # control characters stripped
    assert "\n" not in _safe_basename({"rel_path": "weird\nname.pdf"})
    assert "\t" not in _safe_basename({"rel_path": "tab\tname.pdf"})
    # no leading dot/dotfile behavior
    assert not _safe_basename({"rel_path": ".hidden"}).startswith(".")
    # bounded length
    assert len(_safe_basename({"rel_path": "x" * 500 + ".pdf"})) <= 80
    # all-separator / empty file path → deterministic 'source' fallback
    assert _safe_basename({"rel_path": "///"}) == "source"
    assert _safe_basename({"rel_path": "..."}) == "source"
    # a link source with no ids still yields a safe, separator-free basename
    link = _safe_basename({"source_kind": "email", "domain_ref_id": "msg-1"})
    assert "/" not in link and ".." not in link and link


def test_suffix_preserved_after_sanitization() -> None:
    p = _card_rel_path(_CFG, _detail("deadbeef0000aaaa", "syn-work", "../../x.pdf"))
    assert p.endswith("__deadbeef0000.md")
    assert ".." not in p and "//" not in p


# ----- collision-safety + determinism --------------------------------------------------------
def test_same_source_id_stable_different_id_distinct() -> None:
    d1 = _detail("id1id1id1id1id1", "syn-work", "dir/report.pdf")
    assert _card_rel_path(_CFG, d1) == _card_rel_path(_CFG, d1)  # stable
    d2 = _detail("id2id2id2id2id2", "syn-work", "OTHER/report.pdf")  # same basename, diff id
    assert _card_rel_path(_CFG, d1) != _card_rel_path(_CFG, d2)  # collision-safe


# ----- self-index guard covers routed subfolders ---------------------------------------------
def test_self_index_guard_covers_routed_subfolders() -> None:
    for rel in ("Source Notes/Work/x__id.md", "Source Notes/Home/y__id.md",
                "Source Notes/Shared/z__id.md", "Source Notes/card.md"):
        assert is_source_notes_path(rel, _CFG) is True, rel
    assert is_source_notes_path("Projects/Source Notes Archive/x.md", _CFG) is False


# ----- integration: generate routed card, idempotent, no clobber -----------------------------
def _env(tmp_path: Path, root_key: str = "syn-work"):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    root = tmp_path / "proj"
    (root / "25-244").mkdir(parents=True, exist_ok=True)
    cfg = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": root_key, "path": str(root), "enabled": True}],
    })
    return SourceIndexRepository(db), cfg, root, vault, db


def test_generated_card_routed_and_idempotent(tmp_path: Path) -> None:
    repo, cfg, root, vault, db = _env(tmp_path, "syn-work")
    f = root / "25-244" / "RFI 12 conduit.md"
    f.write_text("Request for Information RFI #12 conduit.", encoding="utf-8")
    sid = index_source_file(f, cfg.external_sources[0], repo, cfg)
    out = generate_source_card(repo, cfg, source_id=sid)
    rel = out["note_path"]
    assert rel.startswith("Source Notes/Work/")          # work root → Work
    assert (vault / rel).is_file()
    card = (vault / rel).read_text(encoding="utf-8")
    assert 'domain: "work"' in card                       # frontmatter domain matches routed folder
    # DB stores the routed path.
    db_path = sqlite3.connect(db).execute(
        "SELECT note_rel_path FROM source_intelligence_generated_notes WHERE source_id=?", (sid,)
    ).fetchone()[0]
    assert db_path == rel
    # Re-generation is idempotent: same path, single row, not duplicated.
    out2 = generate_source_card(repo, cfg, source_id=sid, overwrite=True)
    assert out2["note_path"] == rel
    cnt = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE source_id=?", (sid,)
    ).fetchone()[0]
    assert cnt == 1


def test_user_authored_card_not_overwritten(tmp_path: Path) -> None:
    repo, cfg, root, vault, _db = _env(tmp_path, "syn-work")
    f = root / "25-244" / "Note.md"
    f.write_text("scope", encoding="utf-8")
    sid = index_source_file(f, cfg.external_sources[0], repo, cfg)
    rel = _card_rel_path(cfg, repo.get_source_detail(sid))
    target = vault / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# my own note\nhand written", encoding="utf-8")
    with pytest.raises(ObsidianMcpToolError) as exc:  # overwrite=False must refuse to clobber
        generate_source_card(repo, cfg, source_id=sid, overwrite=False)
    assert exc.value.code == "note_already_exists"
    assert target.read_text(encoding="utf-8") == "# my own note\nhand written"


def test_home_root_routes_home(tmp_path: Path) -> None:
    repo, cfg, root, vault, _db = _env(tmp_path, "syn-home")
    f = root / "25-244" / "Mortgage.md"
    f.write_text("refi terms", encoding="utf-8")
    sid = index_source_file(f, cfg.external_sources[0], repo, cfg)
    out = generate_source_card(repo, cfg, source_id=sid)
    assert out["note_path"].startswith("Source Notes/Home/")


def test_scan_vault_notes_excludes_routed_cards(tmp_path: Path) -> None:
    repo, cfg, _root, vault, _db = _env(tmp_path, "syn-work")
    (vault / "Projects").mkdir()
    (vault / "Projects" / "Scope.md").write_text("# scope", encoding="utf-8")
    for sub in ("Work", "Home", "Shared"):
        d = vault / "Source Notes" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / f"card__{sub}.md").write_text("# generated card", encoding="utf-8")
    scan_vault_notes(repo, cfg)
    active = repo.active_rel_paths("__vault_notes__")
    assert "Projects/Scope.md" in active
    assert not any(p.startswith("Source Notes/") for p in active)
