"""A1.11 — drain prioritization: HIGH before NORMAL, policy skips with codes, no fragile indexing."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import drain_queue
from hb_assistant.store.migrator import SQLiteMigrator


def _make(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **cfg_over):
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
    root.mkdir(parents=True, exist_ok=True)
    base = {
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True, "source_card_auto_generate_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    }
    base.update(cfg_over)
    return SourceIndexRepository(db), ObsidianMcpConfig.model_validate(base), vault, root


def _write(root: Path, rel: str, text: str = "x") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _carded_names(vault: Path) -> set[str]:
    folder = vault / "Source Notes"
    return {f.name for f in folder.rglob("*.md")} if folder.exists() else set()


def test_rebuild_cards_high_before_normal(tmp_path, monkeypatch) -> None:
    repo, config, vault, root = _make(tmp_path, monkeypatch, source_card_auto_max_per_drain=1)
    _write(root, "22-101-00/A-310-PLAN.txt", "WALL SECTIONS")          # high (drawing)
    _write(root, "22-101-00/Marketing Deck.txt", "presentation")        # normal
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    drain_queue(repo, config)  # cap=1 → only the HIGH card
    carded = _carded_names(vault)
    assert any("A-310" in n for n in carded)
    assert not any("Marketing" in n for n in carded)
    while drain_queue(repo, config) > 0:  # resume → normal now carded
        pass
    assert any("Marketing" in n for n in _carded_names(vault))


def test_single_file_metadata_only_is_skipped_not_errored(tmp_path, monkeypatch) -> None:
    repo, config, vault, root = _make(tmp_path, monkeypatch)
    _write(root, "22-101-00/Generic Workbook.xlsx", "rows")
    # xlsx parse needs openpyxl; index still records the source even if extraction is empty.
    repo.enqueue_event(event_type="created", rel_path="22-101-00/Generic Workbook.xlsx",
                       source_root_key="proj")
    drain_queue(repo, config)
    status = repo.index_status()
    assert status["error_count"] == 0
    assert status["skipped_count"] >= 1
    assert "metadata_only_no_auto_card" in status["skipped_by_code"]
    assert _carded_names(vault) == set()


def test_unsupported_event_skipped_without_indexing(tmp_path, monkeypatch) -> None:
    repo, config, vault, root = _make(tmp_path, monkeypatch)
    _write(root, "22-101-00/Portal.url", "[InternetShortcut]\nURL=https://x")
    repo.enqueue_event(event_type="created", rel_path="22-101-00/Portal.url", source_root_key="proj")
    drain_queue(repo, config)
    status = repo.index_status()
    assert status["error_count"] == 0
    assert "unsupported_file_type" in status["skipped_by_code"]
    # Unsupported types are NOT indexed (no fragile parsing / garbage rows).
    assert status["sources_total"] == 0
    assert _carded_names(vault) == set()


def test_deferred_event_indexed_but_not_carded(tmp_path, monkeypatch) -> None:
    repo, config, vault, root = _make(tmp_path, monkeypatch)
    _write(root, "HB INSURANCE RENEWALS/2026/GL.txt", "insurance")
    repo.enqueue_event(event_type="created", rel_path="HB INSURANCE RENEWALS/2026/GL.txt",
                       source_root_key="proj")
    drain_queue(repo, config)
    status = repo.index_status()
    assert "deferred_path" in status["skipped_by_code"]
    assert status["sources_total"] == 1  # deferred IS indexed for search
    assert _carded_names(vault) == set()


def test_delete_event_produces_no_card(tmp_path, monkeypatch) -> None:
    repo, config, vault, root = _make(tmp_path, monkeypatch)
    repo.enqueue_event(event_type="deleted", rel_path="22-101-00/gone.txt", source_root_key="proj")
    drain_queue(repo, config)
    assert _carded_names(vault) == set()
    assert repo.index_status()["error_count"] == 0
