"""A1.10 Defect 3 — generated Source Notes/ cards must not re-index as vault notes."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import (
    _VAULT_ROOT_KEY,
    drain_queue,
    is_source_notes_path,
    scan_vault_notes,
)
from hb_assistant.obsidian_mcp.source_skip_codes import SOURCE_NOTES_SELF_INDEX_GUARD
from hb_assistant.store.migrator import SQLiteMigrator


def test_is_source_notes_path_default_and_custom() -> None:
    cfg = ObsidianMcpConfig()
    assert is_source_notes_path("Source Notes/foo.md", cfg) is True
    assert is_source_notes_path("Source Notes/22-101/A-312.pdf.md", cfg) is True
    assert is_source_notes_path("Projects/Scope.md", cfg) is False
    assert is_source_notes_path("My Source Notes Backup/x.md", cfg) is False  # not a leading segment
    assert is_source_notes_path("Projects/Source Notes Archive/x.md", cfg) is False  # deeper, not rooted
    custom = ObsidianMcpConfig.model_validate({"source_notes_folder": "Inbox/Cards"})
    assert is_source_notes_path("Inbox/Cards/x.md", config=custom) is True
    assert is_source_notes_path("Source Notes/x.md", config=custom) is False


def test_is_source_notes_path_work_home_shared_subfolders() -> None:
    """Work/Home target architecture: generated cards live under Source Notes/{Work,Home,Shared}."""
    cfg = ObsidianMcpConfig()
    assert is_source_notes_path("Source Notes/Work/22-101/COR-014.pdf.md", cfg) is True
    assert is_source_notes_path("Source Notes/Home/Mortgage/refi.pdf.md", cfg) is True
    assert is_source_notes_path("Source Notes/Shared/Insurance/policy.pdf.md", cfg) is True


def test_is_source_notes_path_case_insensitive() -> None:
    cfg = ObsidianMcpConfig()
    assert is_source_notes_path("source notes/work/card.md", cfg) is True
    assert is_source_notes_path("SOURCE NOTES/Card.md", cfg) is True


def _env(tmp_path: Path, *, source_notes_folder: str = "Source Notes"):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "source_notes_folder": source_notes_folder,
    })
    return SourceIndexRepository(db), cfg, vault


def test_scan_vault_notes_skips_generated_cards_but_indexes_normal_notes(tmp_path: Path) -> None:
    repo, cfg, vault = _env(tmp_path)
    (vault / "Projects").mkdir()
    (vault / "Projects" / "Scope.md").write_text("# Scope\nNormal vault note.", encoding="utf-8")
    card_dir = vault / "Source Notes" / "22-101-00"
    card_dir.mkdir(parents=True)
    (card_dir / "A-312.pdf.md").write_text("# Source Card\nGenerated card.", encoding="utf-8")

    scan_vault_notes(repo, cfg)
    active = repo.active_rel_paths("__vault_notes__")
    assert "Projects/Scope.md" in active
    assert not any("Source Notes" in p for p in active)


def test_custom_source_notes_folder_is_honored_in_scan(tmp_path: Path) -> None:
    repo, cfg, vault = _env(tmp_path, source_notes_folder="Inbox/Cards")
    (vault / "Inbox" / "Cards").mkdir(parents=True)
    (vault / "Inbox" / "Cards" / "card.md").write_text("# card", encoding="utf-8")
    (vault / "Source Notes").mkdir()  # NOT the configured folder → should index
    (vault / "Source Notes" / "note.md").write_text("# normal", encoding="utf-8")

    scan_vault_notes(repo, cfg)
    active = repo.active_rel_paths("__vault_notes__")
    assert "Source Notes/note.md" in active           # not the configured card folder
    assert not any(p.startswith("Inbox/Cards") for p in active)


def _drain_env(tmp_path: Path):
    """DB + config with one external root 'proj' and a vault root, for drain-path guard tests."""
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    cfg = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    return SourceIndexRepository(db), cfg, vault, root


def test_drain_skips_vault_source_notes_event(tmp_path: Path) -> None:
    """A queued VAULT-root event under Source Notes is a clean self-index-guard skip (not indexed)."""
    repo, cfg, _vault, _root = _drain_env(tmp_path)
    repo.enqueue_event(event_type="modified", rel_path="Source Notes/Work/card.md",
                       source_root_key=_VAULT_ROOT_KEY)
    drain_queue(repo, cfg)
    status = repo.index_status()
    assert status["skipped_by_code"].get(SOURCE_NOTES_SELF_INDEX_GUARD) == 1
    # The generated card was NOT indexed as a source.
    assert repo.lookup_by_path("external_file", "Source Notes/Work/card.md") is None


def test_drain_does_not_skip_external_root_named_source_notes(tmp_path: Path) -> None:
    """An EXTERNAL root that legitimately contains a 'Source Notes' folder is indexed, NOT skipped.

    The self-index guard is scoped to the vault root only; it must never suppress real external
    source files merely because their path contains 'Source Notes'.
    """
    repo, cfg, _vault, root = _drain_env(tmp_path)
    (root / "Source Notes").mkdir(parents=True)
    (root / "Source Notes" / "foo.md").write_text("Real external doc about conduit", encoding="utf-8")
    repo.enqueue_event(event_type="modified", rel_path="Source Notes/foo.md", source_root_key="proj")
    drain_queue(repo, cfg)
    # Indexed as a normal external file; the self-index-guard skip code never fired.
    assert repo.lookup_by_path("external_file", "Source Notes/foo.md") is not None
    assert SOURCE_NOTES_SELF_INDEX_GUARD not in repo.index_status()["skipped_by_code"]
