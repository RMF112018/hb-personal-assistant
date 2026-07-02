"""Phase 10L-A: guarded generated-artifact DB reset (status -> not_generated).

Proves dry-run identifies missing-file candidates; apply (temp DB) resets only those rows to
not_generated with a mandatory backup, leaving source rows and the queue unchanged; apply refuses
without backup/confirm flags; a reset row does NOT block later regeneration (amendment); and advisory
summaries are only reset for unambiguously-orphaned sources.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import _card_rel_path, generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

_REPO = Path(__file__).resolve().parents[1]
_NOW = "2026-07-02T00:00:00+00:00"


def _load():
    spec = importlib.util.spec_from_file_location(
        "obsidian_generated_artifact_db_reset", _REPO / "scripts" / "obsidian_generated_artifact_db_reset.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _setup(tmp_path: Path) -> tuple[str, ObsidianMcpConfig, Path, SourceIndexRepository]:
    db = str(tmp_path / "x.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    root.mkdir()
    vault = tmp_path / "vault"
    (vault / "Source Notes" / "Work").mkdir(parents=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "writes_enabled": True, "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "onedrive-work", "path": str(root), "enabled": True}],
    })
    return db, config, vault, SourceIndexRepository(db)


def _index(root: Path, config: ObsidianMcpConfig, repo: SourceIndexRepository, rel: str) -> str:
    abs_path = root / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(f"body of {rel}", encoding="utf-8")
    sid = index_source_file(abs_path, config.external_sources[0], repo, config)
    assert sid is not None
    card_rel = _card_rel_path(config, repo.get_source_detail(sid))
    repo.record_generated_note(sid, card_rel, "generated", _NOW)
    return sid


def test_dry_run_identifies_missing_and_does_not_mutate(tmp_path: Path) -> None:
    mod = _load()
    db, config, vault, repo = _setup(tmp_path)
    _index(tmp_path / "proj", config, repo, "b.md")  # no vault card file -> missing
    before = mod._counts(db)
    rc = mod.main(["--db-path", db, "--vault-path", str(vault)])
    assert rc == 0
    assert mod._counts(db) == before  # dry-run mutates nothing
    sel = mod.select_candidates(db, vault)
    assert len(sel["candidates"]) == 1


def test_apply_resets_only_missing_and_keeps_sources_and_queue(tmp_path: Path) -> None:
    mod = _load()
    db, config, vault, repo = _setup(tmp_path)
    sid_missing = _index(tmp_path / "proj", config, repo, "missing.md")
    sid_present = _index(tmp_path / "proj", config, repo, "present.md")
    card_present = _card_rel_path(config, repo.get_source_detail(sid_present))
    (vault / card_present).parent.mkdir(parents=True, exist_ok=True)
    (vault / card_present).write_text("card\n", encoding="utf-8")

    before = mod._counts(db)
    backup = tmp_path / "bak" / "db.sqlite"
    rc = mod.main(["--db-path", db, "--vault-path", str(vault), "--apply",
                   "--backup-db-path", str(backup), "--confirm-db-path", db,
                   "--confirm-reset-generated-artifact-rows"])
    assert rc == 0
    assert backup.is_file()
    after = mod._counts(db)
    assert after["source_rows"] == before["source_rows"]
    assert after["queue_queued"] == before["queue_queued"]
    assert after["queue_processing"] == before["queue_processing"]
    assert after["generated_not_generated"] == 1  # exactly the missing one
    assert repo.has_generated_note(sid_present) is True   # present card untouched
    assert repo.has_generated_note(sid_missing) is False  # reset


def test_apply_refuses_without_backup_or_confirm(tmp_path: Path) -> None:
    mod = _load()
    db, config, vault, repo = _setup(tmp_path)
    _index(tmp_path / "proj", config, repo, "b.md")
    # missing backup
    assert mod.main(["--db-path", db, "--vault-path", str(vault), "--apply",
                     "--confirm-db-path", db, "--confirm-reset-generated-artifact-rows"]) == 3
    # missing confirm-reset flag
    assert mod.main(["--db-path", db, "--vault-path", str(vault), "--apply",
                     "--backup-db-path", str(tmp_path / "b.sqlite"), "--confirm-db-path", db]) == 3
    # wrong confirm-db-path
    assert mod.main(["--db-path", db, "--vault-path", str(vault), "--apply",
                     "--backup-db-path", str(tmp_path / "b.sqlite"), "--confirm-db-path", "/wrong",
                     "--confirm-reset-generated-artifact-rows"]) == 3


def test_reset_row_does_not_block_regeneration(tmp_path: Path) -> None:
    """Amendment: a not_generated row must not block later regeneration; the card recreates cleanly."""
    mod = _load()
    db, config, vault, repo = _setup(tmp_path)
    sid = _index(tmp_path / "proj", config, repo, "regen.md")
    backup = tmp_path / "bak" / "db.sqlite"
    assert mod.main(["--db-path", db, "--vault-path", str(vault), "--apply",
                     "--backup-db-path", str(backup), "--confirm-db-path", db,
                     "--confirm-reset-generated-artifact-rows"]) == 0
    assert repo.has_generated_note(sid) is False  # source now looks never-carded

    # Regenerate: manual card generation recreates the card and flips the row back to generated.
    generate_source_card(repo, config, source_id=sid, overwrite=True, principal_kind="local")
    assert repo.has_generated_note(sid) is True
    card_rel = _card_rel_path(config, repo.get_source_detail(sid))
    assert (vault / card_rel).is_file()


def test_summary_reset_only_for_fully_orphaned_sources(tmp_path: Path) -> None:
    mod = _load()
    db, config, vault, repo = _setup(tmp_path)
    receipt = {"model_provider": "ollama", "model_name": "qwen2.5:14b", "prompt_version": "v1",
               "prompt_sha256": None, "summary_sha256": None, "source_sha256": None}

    # Fully-orphaned source: single generated note, file missing, has a summary.
    sid_orphan = _index(tmp_path / "proj", config, repo, "orphan.md")
    repo.upsert_summary(sid_orphan, receipt)

    # Ambiguous source: two generated notes (one present, one missing), has a summary -> left untouched.
    sid_amb = _index(tmp_path / "proj", config, repo, "amb.md")
    present_rel = "Source Notes/Work/amb-present__0123456789ab.md"
    repo.record_generated_note(sid_amb, present_rel, "generated", _NOW)
    (vault / present_rel).parent.mkdir(parents=True, exist_ok=True)
    (vault / present_rel).write_text("card\n", encoding="utf-8")
    repo.upsert_summary(sid_amb, receipt)

    backup = tmp_path / "bak" / "db.sqlite"
    rc = mod.main(["--db-path", db, "--vault-path", str(vault), "--apply",
                   "--backup-db-path", str(backup), "--confirm-db-path", db,
                   "--confirm-reset-generated-artifact-rows", "--also-reset-orphaned-summaries"])
    assert rc == 0
    assert repo.get_summary(sid_orphan) is None      # unambiguously orphaned -> reset
    assert repo.get_summary(sid_amb) is not None      # ambiguous -> left untouched
