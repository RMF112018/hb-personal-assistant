"""A1.10 Defect 4 — safe maintenance op to retire pre-hygiene generated cards."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_maintenance import retire_source_cards
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

INS_REL = "HB INSURANCE RENEWALS/GL/2026 renewal.txt"


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
    # A deferred (insurance) card + a normal card. Both manually generated (so status=generated).
    (root / "HB INSURANCE RENEWALS" / "GL").mkdir(parents=True)
    (root / "HB INSURANCE RENEWALS" / "GL" / "2026 renewal.txt").write_text("policy", encoding="utf-8")
    (root / "22-101-00").mkdir(parents=True)
    (root / "22-101-00" / "scope.txt").write_text("scope", encoding="utf-8")
    sid_ins = index_source_file(root / INS_REL, config.external_sources[0], repo, config)
    sid_ok = index_source_file(root / "22-101-00" / "scope.txt", config.external_sources[0], repo, config)
    out_ins = generate_source_card(repo, config, source_id=sid_ins)
    generate_source_card(repo, config, source_id=sid_ok)
    return repo, config, vault, db, sid_ins, out_ins["note_path"]


def _status(db: str, source_id: str) -> str:
    return sqlite3.connect(db).execute(
        "SELECT generation_status FROM source_intelligence_generated_notes WHERE source_id=?",
        (source_id,),
    ).fetchone()[0]


def test_dry_run_returns_counts_and_samples_without_mutation(env) -> None:
    repo, config, vault, db, sid_ins, note_path = env
    res = retire_source_cards(repo, config, apply=False)
    assert res["apply"] is False
    assert res["matched_count"] == 1  # only the insurance (deferred) card matches (via source_rel)
    assert res["by_policy"]["deferred"] == 1
    # Phase 5: cards are domain-routed (no source-dir replication), so the deferred match comes from
    # the source path, and the sampled path is the routed card path (no leaked source directory).
    assert note_path in res["sample_paths"]
    assert res["retired_count"] == 0
    # No DB change, card file untouched.
    assert _status(db, sid_ins) == "generated"
    assert (vault / note_path).exists()


def test_apply_marks_stale_keeps_source_and_file(env) -> None:
    repo, config, vault, db, sid_ins, note_path = env
    res = retire_source_cards(repo, config, apply=True)
    assert res["retired_count"] == 1
    assert res["files_deleted"] == 0  # delete_files not set
    assert _status(db, sid_ins) == "stale"
    # Source row intact; card file still present (only the row was retired).
    assert repo.lookup_by_path("external_file", INS_REL) is not None
    assert (vault / note_path).exists()


def test_delete_files_removes_only_the_card_file(env) -> None:
    repo, config, vault, db, sid_ins, note_path = env
    assert (vault / note_path).exists()
    res = retire_source_cards(repo, config, apply=True, delete_files=True)
    assert res["retired_count"] == 1 and res["files_deleted"] == 1
    assert not (vault / note_path).exists()           # card file removed
    assert repo.lookup_by_path("external_file", INS_REL) is not None  # source row intact
    assert _status(db, sid_ins) == "stale"


def test_retire_matches_manual_test_card(env) -> None:
    # A1.11: test/manual cards (path signal 'source-summary-test') are retire-eligible too.
    repo, config, vault, db, sid_ins, _note = env
    root = Path(config.external_sources[0].path)
    (root / "manual").mkdir(parents=True, exist_ok=True)
    (root / "manual" / "source-summary-test.txt").write_text("test card", encoding="utf-8")
    sid_test = index_source_file(root / "manual" / "source-summary-test.txt",
                                 config.external_sources[0], repo, config)
    generate_source_card(repo, config, source_id=sid_test)

    res = retire_source_cards(repo, config, apply=False)
    assert res["by_policy"]["test"] == 1
    assert res["by_policy"]["deferred"] == 1  # insurance still matches
    assert any("source-summary-test" in p for p in res["sample_paths"])
    # Apply marks only those stale; the normal scope card is untouched.
    res2 = retire_source_cards(repo, config, apply=True)
    assert res2["retired_count"] == 2
    assert _status(db, sid_test) == "stale"
