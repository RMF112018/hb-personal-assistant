"""A1.8 Slice 1 — bulk-rebuild auto-generation plumbing (cards/summaries, caps, sensitivity)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import llm
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import drain_queue
from hb_assistant.store.migrator import SQLiteMigrator


class _FakeBackend:
    def generate_json(self, *, system: str, prompt: str) -> str:
        return json.dumps({"plain_english_summary": "x", "what_this_sheet_is_for": "y", "confidence": {}})


def _make(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, n_files: int = 3, sensitive: bool = False,
          **cfg_over):
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
    (root / "22-101-00").mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        (root / "22-101-00" / f"A-{310 + i}-SHEET.txt").write_text(
            f"WALL SECTIONS sheet {i}\nWaterproofing and vapor barrier.\n", encoding="utf-8"
        )
    base = {
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True,
                              "sensitive": sensitive}],
    }
    base.update(cfg_over)
    config = ObsidianMcpConfig.model_validate(base)
    return SourceIndexRepository(db), config, vault


def _drain_all(repo: SourceIndexRepository, config: ObsidianMcpConfig) -> None:
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    while drain_queue(repo, config) > 0:
        pass


def _card_count(vault: Path) -> int:
    folder = vault / "Source Notes"
    return len(list(folder.rglob("*.md"))) if folder.exists() else 0


def _summarized_count(vault: Path) -> int:
    folder = vault / "Source Notes"
    if not folder.exists():
        return 0
    return sum(1 for f in folder.rglob("*.md") if "summary_advisory: true" in f.read_text(encoding="utf-8"))


def test_rebuild_card_auto_off_indexes_but_no_cards(tmp_path, monkeypatch) -> None:
    repo, config, vault = _make(tmp_path, monkeypatch,
                                source_card_auto_generate_enabled=False,
                                source_note_auto_refresh_enabled=False)
    _drain_all(repo, config)
    assert repo.index_status()["sources_total"] == 3
    assert _card_count(vault) == 0


def test_rebuild_card_auto_on_creates_deterministic_cards(tmp_path, monkeypatch) -> None:
    repo, config, vault = _make(tmp_path, monkeypatch, source_card_auto_generate_enabled=True)
    _drain_all(repo, config)
    assert _card_count(vault) == 3


def test_rebuild_unchanged_sources_do_not_regenerate(tmp_path, monkeypatch) -> None:
    repo, config, vault = _make(tmp_path, monkeypatch, source_card_auto_generate_enabled=True)
    _drain_all(repo, config)
    assert _card_count(vault) == 3
    # Second rebuild with no file changes must not change the card set.
    _drain_all(repo, config)
    assert _card_count(vault) == 3


def test_rebuild_card_cap_is_resumable(tmp_path, monkeypatch) -> None:
    repo, config, vault = _make(tmp_path, monkeypatch, n_files=3,
                                source_card_auto_generate_enabled=True,
                                source_card_auto_max_per_drain=2)
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    drain_queue(repo, config)  # first drain: capped at 2 cards, remainder re-enqueued
    assert _card_count(vault) == 2
    while drain_queue(repo, config) > 0:  # resume the remainder
        pass
    assert _card_count(vault) == 3


def test_rebuild_uses_configured_card_cap_not_default(tmp_path, monkeypatch) -> None:
    """The drain honors the CONFIGURED source_card_auto_max_per_drain (here 1), not the 200 default."""
    repo, config, vault = _make(tmp_path, monkeypatch, n_files=3,
                                source_card_auto_generate_enabled=True,
                                source_card_auto_max_per_drain=1)
    assert config.source_card_auto_max_per_drain == 1  # configured value, not default 200 / None
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    drain_queue(repo, config)  # first drain: exactly one card (the configured cap)
    assert _card_count(vault) == 1
    while drain_queue(repo, config) > 0:  # remainder resumes on later drains
        pass
    assert _card_count(vault) == 3


def test_rebuild_summary_auto_respects_per_drain_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(llm, "_resolve_backend", lambda config: _FakeBackend())
    repo, config, vault = _make(tmp_path, monkeypatch, n_files=3,
                                source_card_auto_generate_enabled=True,
                                source_summary_auto_generate_enabled=True,
                                source_summary_auto_max_per_drain=1)
    _drain_all(repo, config)
    # Cap is per drain; across the full drain loop at most one summary is added per drain pass.
    # With one rebuild event in a single drain, exactly one source is summarized.
    assert _summarized_count(vault) == 1
    assert _card_count(vault) == 3  # deterministic cards still made for all


def test_sensitive_root_gets_cards_but_no_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(llm, "_resolve_backend", lambda config: _FakeBackend())
    repo, config, vault = _make(tmp_path, monkeypatch, sensitive=True,
                                source_card_auto_generate_enabled=True,
                                source_summary_auto_generate_enabled=True)
    _drain_all(repo, config)
    assert _card_count(vault) == 3
    assert _summarized_count(vault) == 0


def test_rebuild_records_generation_telemetry(tmp_path, monkeypatch) -> None:
    repo, config, vault = _make(tmp_path, monkeypatch, source_card_auto_generate_enabled=True)
    _drain_all(repo, config)
    status = repo.index_status()
    assert status["generated_card_count"] == 3
    assert status["last_generation_at"] is not None
    assert status["last_generation_cards"] == "3"
