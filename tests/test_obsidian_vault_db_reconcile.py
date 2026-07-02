"""Phase 10L-A: read-only DB/vault reconciliation reporter.

Proves the reporter counts missing generated-note rows, orphan vault cards, and duplicate content-sha
card groups; keeps runtime state unchanged (read-only); and emits count-only safe output with no
sensitive paths/ids (row-level detail goes to the local-sensitive dir only).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import _card_rel_path
from hb_assistant.store.migrator import SQLiteMigrator

_REPO = Path(__file__).resolve().parents[1]
_NOW = "2026-07-02T00:00:00+00:00"


def _load():
    spec = importlib.util.spec_from_file_location(
        "obsidian_vault_db_reconcile", _REPO / "scripts" / "obsidian_vault_db_reconcile.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _setup(tmp_path: Path) -> tuple[str, ObsidianMcpConfig, Path, SourceIndexRepository]:
    db = str(tmp_path / "r.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    root.mkdir()
    vault = tmp_path / "vault"
    (vault / "Source Notes" / "Work").mkdir(parents=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "external_sources": [{"source_root_key": "onedrive-work", "path": str(root), "enabled": True}],
    })
    return db, config, vault, SourceIndexRepository(db)


def _index(root: Path, config: ObsidianMcpConfig, repo: SourceIndexRepository, rel: str,
           content: str) -> tuple[str, str]:
    """Index a file, record a generated note for it; return (source_id, card_rel_path)."""
    abs_path = root / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    sid = index_source_file(abs_path, config.external_sources[0], repo, config)
    assert sid is not None
    card_rel = _card_rel_path(config, repo.get_source_detail(sid))
    repo.record_generated_note(sid, card_rel, "generated", _NOW)
    return sid, card_rel


def test_reports_missing_present_orphan_and_dup_groups(tmp_path: Path) -> None:
    mod = _load()
    db, config, vault, repo = _setup(tmp_path)
    # present card (file written), missing card (row only), and a duplicate-content pair.
    _sid_p, card_present = _index(root=tmp_path / "proj", config=config, repo=repo,
                                  rel="a.md", content="alpha body")
    (vault / card_present).parent.mkdir(parents=True, exist_ok=True)
    (vault / card_present).write_text("card\n", encoding="utf-8")
    _index(tmp_path / "proj", config, repo, "b.md", content="beta body")  # missing card file
    _index(tmp_path / "proj", config, repo, "dup1.md", content="SAME")
    _index(tmp_path / "proj", config, repo, "dup2.md", content="SAME")  # same content_sha256
    # an orphan vault card with no DB row
    (vault / "Source Notes" / "Work" / "orphan__0123456789ab.md").write_text("x\n", encoding="utf-8")

    out = mod.reconcile(db, vault, "Source Notes")
    safe = out["safe"]
    assert safe["missing_generated_note_rows"] == 3  # b + dup1 + dup2 (files not written)
    assert safe["orphan_vault_cards"] == 1
    assert safe["source_row_count"] == 4
    assert safe["queue_queued"] == 0 and safe["queue_processing"] == 0
    assert safe["duplicate_source_card_groups"] == 1
    assert safe["duplicate_source_card_extra"] == 1


def test_read_only_state_unchanged_and_safe_output_is_countonly(tmp_path: Path) -> None:
    mod = _load()
    db, config, vault, repo = _setup(tmp_path)
    _index(tmp_path / "proj", config, repo, "secret-filename.md", content="body")
    fp_before = mod._state_fingerprint(db)
    ls_dir = tmp_path / "local-sensitive"
    out_json = tmp_path / "safe.json"
    rc = mod.main(["--db-path", db, "--vault-path", str(vault),
                   "--json-output", str(out_json), "--local-sensitive-dir", str(ls_dir)])
    assert rc == 0
    assert mod._state_fingerprint(db) == fp_before  # read-only guarantee

    safe = json.loads(out_json.read_text(encoding="utf-8"))
    assert safe["runtime_state_unchanged"] is True and safe["mode"] == "read_only"
    # Safe output must not leak the source filename or card path.
    blob = out_json.read_text(encoding="utf-8")
    assert "secret-filename" not in blob and "Source Notes/" not in blob
    # Row-level detail is written to local-sensitive only.
    assert (ls_dir / "vault-db-reconcile-detail-local-sensitive.json").is_file()
