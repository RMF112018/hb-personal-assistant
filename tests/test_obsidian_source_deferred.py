"""A1.10 Defect 5 — deferred path policy (indexed/searchable; auto-skipped; distinct from excluded)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import (
    drain_queue,
    index_source_file,
    is_deferred_source_path,
    is_excluded_source_path,
)
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError
from hb_assistant.store.migrator import SQLiteMigrator

INS_REL = "HB INSURANCE RENEWALS/GENERAL LIABILITY/2026 GENERAL LIABILITY RENEWAL 26-27/policy.txt"


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
        "vault_markdown_write_enabled": True, "source_card_auto_generate_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    return SourceIndexRepository(db), config, root, vault, db


def _write(root: Path, rel: str, body: str) -> Path:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return f


def test_deferred_is_distinct_from_excluded() -> None:
    cfg = ObsidianMcpConfig()
    assert is_deferred_source_path(INS_REL, cfg) is True
    assert is_excluded_source_path(INS_REL, cfg) is False
    assert is_deferred_source_path("a/node_modules/x.js", cfg) is False
    assert is_excluded_source_path("a/node_modules/x.js", cfg) is True


def test_deferred_drain_event_indexed_and_skipped_not_error(env) -> None:
    repo, config, root, _vault, db = env
    _write(root, INS_REL, "Insurance renewal policy.")
    repo.enqueue_event(event_type="modified", rel_path=INS_REL, source_root_key="proj")
    drain_queue(repo, config)
    rows = sqlite3.connect(db).execute(
        "SELECT status, error_code FROM source_intelligence_events WHERE event_type='modified'"
    ).fetchall()
    assert rows == [("skipped", "deferred_path")]  # clean skip, NOT error
    # Still indexed/searchable.
    assert repo.lookup_by_path("external_file", INS_REL) is not None


def test_deferred_rebuild_indexes_but_does_not_auto_card(env) -> None:
    repo, config, root, vault, _db = env
    _write(root, INS_REL, "Insurance renewal policy.")
    _write(root, "22-101-00/scope.txt", "Project scope.")
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    while drain_queue(repo, config) > 0:
        pass
    assert repo.lookup_by_path("external_file", INS_REL) is not None  # indexed
    cards = list((vault / "Source Notes").rglob("*.md")) if (vault / "Source Notes").exists() else []
    # Only the non-deferred scope got an auto card.
    assert not any("INSURANCE" in str(c).upper() for c in cards)
    assert any("scope.txt" in str(c) for c in cards)


def test_manual_generate_overrides_deferred_but_excluded_still_raises(env) -> None:
    repo, config, root, vault, _db = env
    sid_ins = index_source_file(_write(root, INS_REL, "Insurance renewal."), config.external_sources[0], repo, config)
    # Deferred: manual generation is an explicit operator override → works.
    out = generate_source_card(repo, config, source_id=sid_ins)
    assert out["status"] == "generated"
    # Excluded: blocked everywhere, even manual.
    sid_nm = index_source_file(_write(root, "node_modules/x/i.d.ts", "export const x:any;"),
                               config.external_sources[0], repo, config)
    with pytest.raises(ObsidianMcpToolError) as exc:
        generate_source_card(repo, config, source_id=sid_nm)
    assert exc.value.code == "source_excluded_path"
