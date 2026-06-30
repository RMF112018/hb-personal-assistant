"""A1.4 — policy-driven auto card/summary generation in drain_queue.

Indexing always succeeds; auto card/summary work is gated by conservative config flags, runs
only on the drain path, suppresses summaries for sensitive roots, caps summaries per drain, and
never fails the index event. Summaries use an injected fake backend (no live Ollama).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import hb_assistant.obsidian_mcp.llm as llm
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import drain_queue
from hb_assistant.store.migrator import SQLiteMigrator

_FAKE_SUMMARY = {
    "summary": "Conduit RFI; 8-week lead time.",
    "key_points": ["8-week lead time"], "action_items": [], "decisions": [],
    "entities": ["conduit"], "suggested_tags": [], "suggested_links": [],
}


class _FakeBackend:
    def generate_json(self, *, system: str, prompt: str) -> str:
        return json.dumps(_FAKE_SUMMARY)


def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **overrides):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root_dir = tmp_path / "proj"
    (root_dir / "22-101-00").mkdir(parents=True, exist_ok=True)
    base = {
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root_dir),
                              "enabled": True, **overrides.pop("root", {})}],
    }
    base.update(overrides)
    config = ObsidianMcpConfig.model_validate(base)
    return SourceIndexRepository(db), config, root_dir, vault, db


def _make_and_enqueue(repo, root_dir: Path, name: str, body: str) -> None:
    f = root_dir / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    repo.enqueue_event(event_type="created", rel_path=name, source_root_key="proj")


def _card_path(vault: Path, rel: str) -> Path:
    # Phase 5: cards are domain-routed to "Source Notes/{Work,Home,Shared}/<basename>__<id12>.md"
    # (no source directory replication). Resolve by the source basename regardless of domain subfolder.
    base = Path(rel).name
    matches = sorted((vault / "Source Notes").rglob(f"{base}__*.md"))
    return matches[0] if matches else vault / "Source Notes" / "__missing__.md"


# ------------------------------------------------------------------------------- defaults: OFF


def test_defaults_index_but_do_not_generate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, config, root_dir, vault, _db = _env(tmp_path, monkeypatch)
    _make_and_enqueue(repo, root_dir, "22-101-00/a.md", "Underground conduit scope.")
    drain_queue(repo, config)
    # indexed...
    assert repo.lookup_by_path("external_file", "22-101-00/a.md") is not None
    # ...but no card written (auto-card default off, and no prior card to refresh)
    assert not _card_path(vault, "22-101-00/a.md").exists()


# ------------------------------------------------------------------------------- card auto-gen


def test_auto_card_generates_on_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, config, root_dir, vault, _db = _env(
        tmp_path, monkeypatch, source_card_auto_generate_enabled=True
    )
    _make_and_enqueue(repo, root_dir, "22-101-00/a.md", "Underground conduit scope.")
    drain_queue(repo, config)
    card = _card_path(vault, "22-101-00/a.md")
    assert card.exists()
    assert "summary_advisory: false" in card.read_text(encoding="utf-8")


def test_auto_card_respects_kind_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, config, root_dir, vault, _db = _env(
        tmp_path, monkeypatch,
        source_card_auto_generate_enabled=True, source_card_auto_generate_kinds=["email"],
    )
    _make_and_enqueue(repo, root_dir, "22-101-00/a.md", "scope")
    drain_queue(repo, config)
    assert not _card_path(vault, "22-101-00/a.md").exists()  # external_file not in kinds


# --------------------------------------------------------------------------------- auto-refresh


def test_auto_refresh_regenerates_existing_card(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # auto-card OFF, auto-refresh ON (default). First generate a card manually, then a modify
    # event should refresh it rather than leave it stale — and NOT create cards for new files.
    repo, config, root_dir, vault, _db = _env(tmp_path, monkeypatch)
    from hb_assistant.obsidian_mcp.source_indexer import index_source_file
    from hb_assistant.obsidian_mcp.source_notes import generate_source_card
    f = root_dir / "22-101-00/a.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("v1 conduit", encoding="utf-8")
    sid = index_source_file(f, config.external_sources[0], repo, config)
    generate_source_card(repo, config, source_id=sid, overwrite=False, principal_kind="local")
    assert repo.has_generated_note(sid)

    f.write_text("v2 conduit revised", encoding="utf-8")
    repo.enqueue_event(event_type="modified", rel_path="22-101-00/a.md", source_root_key="proj")
    drain_queue(repo, config)
    assert "v2 conduit revised" in _card_path(vault, "22-101-00/a.md").read_text(encoding="utf-8")

    # a brand-new file gets NO card under refresh-only policy
    _make_and_enqueue(repo, root_dir, "22-101-00/b.md", "new file")
    drain_queue(repo, config)
    assert not _card_path(vault, "22-101-00/b.md").exists()


# ------------------------------------------------------------------------------------ summaries


def test_auto_summary_generates_with_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_resolve_backend", lambda config: _FakeBackend())
    repo, config, root_dir, vault, _db = _env(
        tmp_path, monkeypatch,
        source_card_auto_generate_enabled=True, source_summary_auto_generate_enabled=True,
    )
    _make_and_enqueue(repo, root_dir, "22-101-00/a.md", "Underground conduit; 8-week lead time.")
    drain_queue(repo, config)
    card = _card_path(vault, "22-101-00/a.md").read_text(encoding="utf-8")
    assert "summary_advisory: true" in card
    assert "## AI Summary" in card


def test_auto_summary_suppressed_for_sensitive_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_resolve_backend", lambda config: _FakeBackend())
    repo, config, root_dir, vault, _db = _env(
        tmp_path, monkeypatch,
        source_card_auto_generate_enabled=True, source_summary_auto_generate_enabled=True,
        root={"sensitive": True},
    )
    _make_and_enqueue(repo, root_dir, "22-101-00/a.md", "Confidential conduit pricing.")
    drain_queue(repo, config)
    card = _card_path(vault, "22-101-00/a.md").read_text(encoding="utf-8")
    assert "summary_advisory: false" in card  # card yes, advisory no
    assert "## AI Summary" not in card


def test_auto_summary_per_drain_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    real = llm.summarize

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(llm, "_resolve_backend", lambda config: _FakeBackend())
    monkeypatch.setattr(llm, "summarize", _counting)
    repo, config, root_dir, _vault, _db = _env(
        tmp_path, monkeypatch,
        source_card_auto_generate_enabled=True, source_summary_auto_generate_enabled=True,
        source_summary_auto_max_per_drain=2,
    )
    for i in range(5):
        _make_and_enqueue(repo, root_dir, f"22-101-00/f{i}.md", f"conduit file {i}")
    drain_queue(repo, config)
    assert calls["n"] == 2  # capped at 2 advisory summaries per drain


def test_auto_gen_failure_does_not_error_index_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force card generation to blow up; the index event must still complete 'done', not 'error'.
    import hb_assistant.obsidian_mcp.source_notes as source_notes

    def _boom(*a, **k):
        raise RuntimeError("card boom")

    monkeypatch.setattr(source_notes, "generate_source_card", _boom)
    repo, config, root_dir, _vault, _db = _env(
        tmp_path, monkeypatch, source_card_auto_generate_enabled=True
    )
    _make_and_enqueue(repo, root_dir, "22-101-00/a.md", "scope")
    drain_queue(repo, config)
    health = repo.queue_health()
    assert health["error_count"] == 0
    assert health["done_count"] == 1
    assert repo.lookup_by_path("external_file", "22-101-00/a.md") is not None
