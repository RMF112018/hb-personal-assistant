"""Phase B / B4 — conservative, transactional same-root rename/move lineage.

Proves: a confirmed same-root move links old->new identity via ``renamed_from_source_id`` in ONE
transaction (old row not non-current unless the destination + lineage persist), content trust is NOT
carried forward (extraction invalidated, generated notes inherited-but-unverified), an old source_ref
answers ``moved`` (with the lineage-lookup ordered before the generic deleted branch), cross-root /
unconfirmed moves stay conservative, and the watcher helper only correlates a confirmed same-root move.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_connector_service as svc
from hb_assistant.obsidian_mcp import source_watch
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_connector_models import encode_source_ref
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository, source_id_for
from hb_assistant.store.migrator import SQLiteMigrator

_NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _insert_source(db: str, *, root_key: str, rel_path: str, ext: str = "txt",
                   with_note: bool = False) -> str:
    sid = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (sid, "external_file", root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_metadata(source_id,file_ext,size_bytes,mtime_ns,"
                  "content_sha256,extraction_status,fts_rowid,indexed_at) VALUES(?,?,?,?,?,?,NULL,?)",
                  (sid, ext, 10, 111, "d", "ok", _NOW))
        if with_note:
            c.execute("INSERT INTO source_intelligence_generated_notes(generated_note_id,source_id,"
                      "note_rel_path,generation_status,generated_at,updated_at) VALUES(?,?,?,?,?,?)",
                      ("n1", sid, "Source Notes/old.md", "generated", _NOW, _NOW))
        c.commit()
    return sid


def _trust(db: str, config: ObsidianMcpConfig, root_key: str) -> None:
    import hashlib

    from hb_assistant.obsidian_mcp.source_indexer import _root_fingerprint

    cfg_root = next(r for r in config.external_sources if r.source_root_key == root_key)
    fp = _root_fingerprint(cfg_root, config)
    rph = hashlib.sha256(str(Path(cfg_root.path)).encode()).hexdigest()[:32]
    with sqlite3.connect(db) as c:
        c.execute("INSERT OR REPLACE INTO source_index_scan_generations(generation_id,root_key,status,"
                  "root_path_hash,policy_fingerprint,started_at,updated_at,metadata_walk_completed_at,"
                  "reconciliation_completed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (f"gen-{root_key}", root_key, "completed", rph, fp, _NOW, _NOW, _NOW, _NOW, _NOW))
        c.commit()


def _row(db: str, sid: str):
    with sqlite3.connect(db) as c:
        return c.execute("SELECT deleted, active, renamed_from_source_id FROM "
                         "source_intelligence_sources WHERE source_id=?", (sid,)).fetchone()


@pytest.fixture()
def db(tmp_path: Path) -> str:
    d = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=d).apply()
    return d


# ---------------- transactional move op ----------------

def test_confirmed_move_links_and_invalidates(db) -> None:
    repo = SourceIndexRepository(db)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt", with_note=True)
    res = repo.apply_confirmed_same_root_move("work", "a/old.txt", "a/new.txt",
                                              {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 222})
    new = res["new_source_id"]
    assert res["linked"] is True
    # old row is now non-current; new row carries lineage
    assert _row(db, old)[0] == 1  # deleted
    assert _row(db, new)[2] == old  # renamed_from_source_id
    assert _row(db, new)[0] == 0 and _row(db, new)[1] == 1  # current
    # content trust NOT carried: destination extraction is pending
    with sqlite3.connect(db) as c:
        status = c.execute("SELECT extraction_status FROM source_intelligence_metadata WHERE source_id=?",
                           (new,)).fetchone()[0]
        note = c.execute("SELECT source_id, generation_status FROM source_intelligence_generated_notes "
                         "WHERE generated_note_id='n1'").fetchone()
    assert status == "pending"
    # generated note is inherited-but-unverified on the NEW row (explicit 'stale' status)
    assert note == (new, "stale")
    assert repo.find_successor_source_id(old) == new


def test_move_rolls_back_and_keeps_old_current(db, monkeypatch) -> None:
    repo = SourceIndexRepository(db)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    new_sid = source_id_for("external_file", source_root_key="work", rel_path="a/new.txt")
    # Force the final step (old-row delete) to fail AFTER the destination inserts -> whole txn rolls back.
    def _boom(*a, **k):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(repo, "_mark_deleted_by_source_id_locked", _boom)
    with pytest.raises(RuntimeError):
        repo.apply_confirmed_same_root_move("work", "a/old.txt", "a/new.txt",
                                            {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 222})
    # Invariant: old row stays current, and NO partial destination/lineage row was left behind.
    assert _row(db, old) == (0, 1, None)
    assert _row(db, new_sid) is None


def test_move_without_old_row_is_plain_create(db) -> None:
    repo = SourceIndexRepository(db)
    res = repo.apply_confirmed_same_root_move("work", "a/missing.txt", "a/new.txt",
                                              {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 222})
    assert res["linked"] is False
    assert _row(db, res["new_source_id"])[2] is None  # no fabricated predecessor


# ---------------- old source_ref -> moved (lookup ordering) ----------------

def _env_with_move(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="work", path=str(tmp_path))])
    _trust(db, config, "work")
    repo = SourceIndexRepository(db)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    res = repo.apply_confirmed_same_root_move("work", "a/old.txt", "a/new.txt",
                                              {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 222})
    return db, config, repo, old, res["new_source_id"]


def test_old_ref_answers_moved_with_successor(tmp_path) -> None:
    db, config, repo, old, new = _env_with_move(tmp_path)
    r = svc.read_source_file(repo, config, source_ref=encode_source_ref(old), mode="complete")
    assert r["retrieval_state"] == "moved"
    assert r["successor_source_ref"] == encode_source_ref(new)
    assert r["content"] is None and r["completeness_state"] == "none"


def test_moved_successor_outside_authorization_not_disclosed(tmp_path) -> None:
    db, config, repo, old, new = _env_with_move(tmp_path)
    # Make the successor's root sensitive -> successor must not be disclosed; falls back to unavailable.
    config.external_sources[0].sensitive = True
    r = svc.read_source_file(repo, config, source_ref=encode_source_ref(old), mode="complete")
    assert r["retrieval_state"] == "unavailable"
    assert "successor_source_ref" not in r


def test_non_current_successor_not_fabricated_move(tmp_path) -> None:
    db, config, repo, old, new = _env_with_move(tmp_path)
    with sqlite3.connect(db) as c:  # successor itself deleted -> no current successor
        c.execute("UPDATE source_intelligence_sources SET deleted=1, active=0 WHERE source_id=?", (new,))
        c.commit()
    r = svc.read_source_file(repo, config, source_ref=encode_source_ref(old), mode="complete")
    assert r["retrieval_state"] == "unavailable"


def test_plain_deleted_without_lineage_is_unavailable(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(external_sources=[ExternalSourceRoot(source_root_key="work", path=str(tmp_path))])
    _trust(db, config, "work")
    repo = SourceIndexRepository(db)
    sid = _insert_source(db, root_key="work", rel_path="a/gone.txt")
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_sources SET deleted=1, active=0 WHERE source_id=?", (sid,))
        c.commit()
    r = svc.read_source_file(repo, config, source_ref=encode_source_ref(sid), mode="complete")
    assert r["retrieval_state"] == "unavailable"


# ---------------- watcher helper: confirmed same-root vs conservative ----------------

def test_watcher_helper_confirmed_same_root_move(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "work"
    (root / "a").mkdir(parents=True)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    dest = root / "a" / "new.txt"
    dest.write_text("moved content")
    repo = SourceIndexRepository(db)
    handled = source_watch.apply_same_root_move(repo, "work", root, str(root / "a" / "old.txt"), str(dest))
    assert handled is True
    assert repo.find_successor_source_id(old) is not None
    assert _row(db, old)[0] == 1  # old marked deleted via the transactional op


def test_watcher_helper_unconfirmed_dest_is_conservative(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "work"
    (root / "a").mkdir(parents=True)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    repo = SourceIndexRepository(db)
    # destination does NOT exist on disk -> helper must NOT correlate (conservative fallback)
    handled = source_watch.apply_same_root_move(repo, "work", root, str(root / "a" / "old.txt"),
                                                str(root / "a" / "new.txt"))
    assert handled is False
    assert _row(db, old)[0] == 0  # old row untouched (no unsafe delete)


def test_watcher_helper_vault_root_not_correlated(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "vault"
    root.mkdir(exist_ok=True)
    (root / "new.txt").write_text("x")
    repo = SourceIndexRepository(db)
    from hb_assistant.obsidian_mcp.source_indexer import _VAULT_ROOT_KEY  # noqa: PLC0415

    handled = source_watch.apply_same_root_move(repo, _VAULT_ROOT_KEY, root, str(root / "old.txt"),
                                                str(root / "new.txt"))
    assert handled is False
