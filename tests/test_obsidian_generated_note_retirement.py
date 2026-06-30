"""Generated-note retirement: narrow status transition generated|stale -> not_generated.

Temp SQLite DBs + temp vaults only. Never touches production data.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "retire_stale_obsidian_generated_notes.py"
_spec = importlib.util.spec_from_file_location("retire_stale_obsidian_generated_notes", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _insert_note(db: str, gid: str, rel: str | None, status: str) -> None:
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO source_intelligence_generated_notes "
            "(generated_note_id, source_id, note_rel_path, generation_status, generated_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (gid, f"src-{gid}", rel, status, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        c.commit()


def _env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "Obsidian Vault"
    (vault / "Source Notes").mkdir(parents=True)
    # Row whose card file STILL EXISTS (active) → must NOT be retired.
    (vault / "Source Notes" / "keep.md").write_text("# keep", encoding="utf-8")
    _insert_note(db, "g-keep", "Source Notes/keep.md", "generated")
    # Rows whose card files are MISSING (pre-reset) → candidates.
    _insert_note(db, "g-gone1", "Source Notes/22-101/gone1.md", "generated")
    _insert_note(db, "s-gone2", "Source Notes/22-101/gone2.md", "stale")
    # Invalid paths → skipped, never written.
    _insert_note(db, "bad-abs", "/abs/escape.md", "stale")
    _insert_note(db, "bad-dotdot", "Source Notes/../escape.md", "stale")
    # Not under the Source Notes folder → skipped.
    _insert_note(db, "not-folder", "Work/notes/other.md", "stale")
    return db, vault


def _args(db, vault, *extra):
    return ["--db-path", db, "--active-vault-path", str(vault), "--source-notes-folder", "Source Notes",
            "--quarantine-path", "/q/Obsidian Vault - QUARANTINED - X", *extra]


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    db, vault = _env(tmp_path)
    before = mod._status_counts(db)
    rc = mod.main(_args(db, vault, "--evidence-dir", str(tmp_path / "ev")))
    assert rc == 0
    assert mod._status_counts(db) == before  # no mutation


def test_candidate_selection(tmp_path: Path) -> None:
    db, vault = _env(tmp_path)
    sel = mod.select_candidates(db, vault, "Source Notes")
    cand_ids = {c["generated_note_id"] for c in sel["candidates"]}
    assert cand_ids == {"g-gone1", "s-gone2"}                 # missing-file rows only
    assert {x["generated_note_id"] for x in sel["skipped_file_exists"]} == {"g-keep"}
    assert {x["generated_note_id"] for x in sel["skipped_invalid_path"]} == {"bad-abs", "bad-dotdot"}
    assert {x["generated_note_id"] for x in sel["skipped_not_under_folder"]} == {"not-folder"}


def test_apply_refuses_without_confirmations(tmp_path: Path) -> None:
    db, vault = _env(tmp_path)
    before = mod._status_counts(db)
    rc = mod.main(_args(db, vault, "--apply"))  # no --confirm-*
    assert rc == 3
    assert mod._status_counts(db) == before


def test_apply_refuses_when_backend_listening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, vault = _env(tmp_path)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: True)
    rc = mod.main(_args(db, vault, "--apply",
                        "--confirm-db-path", db, "--confirm-active-vault-path", str(vault),
                        "--confirm-quarantine-path", "/q/Obsidian Vault - QUARANTINED - X"))
    assert rc == 3


def test_apply_refuses_when_queue_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, vault = _env(tmp_path)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO source_intelligence_events "
            "(event_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
            "VALUES ('e1','x/y.md','proj','modified','queued',0,'t','t')")
        c.commit()
    rc = mod.main(_args(db, vault, "--apply",
                        "--confirm-db-path", db, "--confirm-active-vault-path", str(vault),
                        "--confirm-quarantine-path", "/q/Obsidian Vault - QUARANTINED - X"))
    assert rc == 3


def test_apply_retires_only_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, vault = _env(tmp_path)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    rc = mod.main(_args(db, vault, "--apply", "--evidence-dir", str(tmp_path / "ev"),
                        "--confirm-db-path", db, "--confirm-active-vault-path", str(vault),
                        "--confirm-quarantine-path", "/q/Obsidian Vault - QUARANTINED - X"))
    assert rc == 0
    with sqlite3.connect(db) as c:
        rows = dict(c.execute(
            "SELECT generated_note_id, generation_status FROM source_intelligence_generated_notes").fetchall())
    assert rows["g-gone1"] == "not_generated"
    assert rows["s-gone2"] == "not_generated"
    assert rows["g-keep"] == "generated"        # active file preserved
    assert rows["bad-abs"] == "stale"           # invalid path untouched
    assert rows["bad-dotdot"] == "stale"
    assert rows["not-folder"] == "stale"


def test_transition_clears_generated_and_stale_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, vault = _env(tmp_path)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    repo = SourceIndexRepository(db)
    st0 = repo.index_status()
    # Baseline: g-keep + g-gone1 generated (2), s-gone2 + bad-abs + bad-dotdot + not-folder stale (4).
    assert st0["generated_card_count"] == 2
    mod.main(_args(db, vault, "--apply",
                   "--confirm-db-path", db, "--confirm-active-vault-path", str(vault),
                   "--confirm-quarantine-path", "/q/Obsidian Vault - QUARANTINED - X"))
    st1 = repo.index_status()
    # g-gone1 (generated) and s-gone2 (stale) retired → both counts drop by 1.
    assert st1["generated_card_count"] == st0["generated_card_count"] - 1
    assert st1["stale_note_count"] == st0["stale_note_count"] - 1


def test_not_generated_not_a_stale_refresh_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, vault = _env(tmp_path)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    repo = SourceIndexRepository(db)
    mod.main(_args(db, vault, "--apply",
                   "--confirm-db-path", db, "--confirm-active-vault-path", str(vault),
                   "--confirm-quarantine-path", "/q/Obsidian Vault - QUARANTINED - X"))
    stale = {r["note_rel_path"] for r in repo.list_stale_generated_notes(limit=100)}
    assert "Source Notes/22-101/gone2.md" not in stale  # retired row is not a refresh candidate


def test_schema_insufficient_stops(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.sqlite")
    sqlite3.connect(db).close()  # no source-intelligence tables
    rc = mod.main(["--db-path", db, "--active-vault-path", str(tmp_path / "v"),
                   "--source-notes-folder", "Source Notes"])
    assert rc == 3


def test_safe_summary_has_no_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, vault = _env(tmp_path)
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    ev = tmp_path / "ev"
    mod.main(_args(db, vault, "--apply", "--evidence-dir", str(ev),
                   "--confirm-db-path", db, "--confirm-active-vault-path", str(vault),
                   "--confirm-quarantine-path", "/q/Obsidian Vault - QUARANTINED - X"))
    safe = (ev / "generated-note-retirement-apply-summary-safe.json").read_text()
    payload = json.loads(safe)
    assert payload["candidate_count"] == 2 and payload["retired_count"] == 2
    # No path-like content in the safe summary.
    for token in ("Source Notes/", "/Users/", "Obsidian Vault", "/abs/"):
        assert token not in safe, token
