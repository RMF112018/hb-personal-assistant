"""A1.10 Defect 3 — generated Source Notes/ cards must not re-index as vault notes."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import is_source_notes_path, scan_vault_notes
from hb_assistant.store.migrator import SQLiteMigrator


def test_is_source_notes_path_default_and_custom() -> None:
    cfg = ObsidianMcpConfig()
    assert is_source_notes_path("Source Notes/foo.md", cfg) is True
    assert is_source_notes_path("Source Notes/22-101/A-312.pdf.md", cfg) is True
    assert is_source_notes_path("Projects/Scope.md", cfg) is False
    assert is_source_notes_path("My Source Notes Backup/x.md", cfg) is False  # not a leading segment
    custom = ObsidianMcpConfig.model_validate({"source_notes_folder": "Inbox/Cards"})
    assert is_source_notes_path("Inbox/Cards/x.md", config=custom) is True
    assert is_source_notes_path("Source Notes/x.md", config=custom) is False


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
