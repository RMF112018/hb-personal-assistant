"""PI-WI-03a (ADR-003 R11-D1/D3) — degraded, decomposed relocation; NO runtime rename lineage.

Under the accepted R11 the ``renamed_from_source_id`` lineage authority is removed from runtime (P-C):
a no-signal relocation is a decomposed **P2 tombstone-old + P1 create-new** (the destination P1 is the
drain's own re-index), ``find_successor_source_id`` always returns None (P-B), and an old (deleted) ref
therefore answers ordinary *unavailable* — never ``moved`` (a signalled-P4 moved answer is 03b). This
suite replaces the former B4 lineage tests with the R11 contract at the repository + provider surface.
"""

from __future__ import annotations

import sqlite3
import uuid
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
    """Seed a LIVE indexed file entity (entity + current locator + parent + metadata). Returns the
    durable source_entity_id."""
    legacy = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    eid = uuid.uuid4().hex
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_index_entities(source_entity_id,created_at,status) "
                  "VALUES(?,?, 'LIVE')", (eid, _NOW))
        c.execute("INSERT INTO source_index_locators(locator_id,source_entity_id,source_id,"
                  "source_root_key,rel_path,is_current_locator,tombstoned_at,generation_seq) "
                  "VALUES(?,?,?,?,?,1,NULL,0)", (uuid.uuid4().hex, eid, legacy, root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_sources(source_entity_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (eid, "external_file", root_key, rel_path))
        c.execute("INSERT INTO source_intelligence_metadata(source_entity_id,file_ext,size_bytes,"
                  "mtime_ns,content_sha256,extraction_status,fts_rowid,indexed_at) "
                  "VALUES(?,?,?,?,?,?,NULL,?)", (eid, ext, 10, 111, "d", "ok", _NOW))
        if with_note:
            c.execute("INSERT INTO source_intelligence_generated_notes(generated_note_id,"
                      "source_entity_id,note_rel_path,generation_status,generated_at,updated_at) "
                      "VALUES(?,?,?,?,?,?)", ("n1", eid, "Source Notes/old.md", "generated", _NOW, _NOW))
        c.commit()
    return eid


def _entity_for(db: str, root_key: str, rel_path: str) -> str | None:
    legacy = source_id_for("external_file", source_root_key=root_key, rel_path=rel_path)
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT DISTINCT source_entity_id FROM source_index_locators WHERE source_id=?",
                         (legacy,)).fetchall()
    return rows[0][0] if len(rows) == 1 else None


def _row(db: str, entity_id: str):
    """(deleted, active, entity_status) for an entity, or None."""
    with sqlite3.connect(db) as c:
        return c.execute(
            "SELECT s.deleted, s.active, e.status FROM source_intelligence_sources s "
            "JOIN source_index_entities e ON e.source_entity_id = s.source_entity_id "
            "WHERE s.source_entity_id=?", (entity_id,)).fetchone()


def _has_renamed_from_writes(db: str) -> int:
    with sqlite3.connect(db) as c:
        return c.execute("SELECT COUNT(*) FROM source_intelligence_sources "
                         "WHERE renamed_from_source_id IS NOT NULL").fetchone()[0]


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


@pytest.fixture()
def db(tmp_path: Path) -> str:
    d = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=d).apply()
    return d


# ---------------- R11-D3 decomposed move op (repository surface) ----------------

def test_confirmed_move_tombstones_old_no_lineage(db) -> None:
    repo = SourceIndexRepository(db)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt", with_note=True)
    res = repo.apply_confirmed_same_root_move("work", "a/old.txt", "a/new.txt",
                                              {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 222})
    assert res["result"] == "move_applied" and res["linked"] is True
    # source side only: the old entity is P2-TOMBSTONED; NO destination entity was created by the move op
    # (the drain's re-index establishes the destination P1).
    assert _row(db, old)[0] == 1 and _row(db, old)[2] == "TOMBSTONED"
    assert _entity_for(db, "work", "a/new.txt") is None
    # NO lineage written; find_successor is always None (R11-D1).
    assert _has_renamed_from_writes(db) == 0
    assert repo.find_successor_source_id(old) is None
    # the old legacy handle still resolves (via the DISTINCT resolver, separately) to the ORIGINAL
    # tombstoned entity — never to a "successor".
    assert repo.resolve_entity(source_id=source_id_for("external_file", source_root_key="work",
                                                       rel_path="a/old.txt")) == old


def test_confirmed_move_conflicting_successor_no_mutation(db) -> None:
    # old is still current AND a live entity already occupies the destination → conservative conflict.
    repo = SourceIndexRepository(db)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    dst = _insert_source(db, root_key="work", rel_path="a/dest.txt")
    res = repo.apply_confirmed_same_root_move("work", "a/old.txt", "a/dest.txt",
                                              {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 2})
    assert res["result"] == "conflicting_successor" and res["linked"] is False
    assert _row(db, old)[0] == 0 and _row(db, dst)[0] == 0  # nothing mutated


def test_confirmed_move_source_missing_no_mutation(db) -> None:
    repo = SourceIndexRepository(db)
    res = repo.apply_confirmed_same_root_move("work", "a/missing.txt", "a/new.txt",
                                              {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 2})
    assert res["result"] == "source_missing" and res["linked"] is False
    assert _entity_for(db, "work", "a/new.txt") is None


def test_confirmed_move_already_applied_when_dest_occupied_old_gone(db) -> None:
    # old absent, destination already occupied by a live entity → P2 no-op, compatibility string only.
    repo = SourceIndexRepository(db)
    _insert_source(db, root_key="work", rel_path="a/dest.txt")
    res = repo.apply_confirmed_same_root_move("work", "a/gone.txt", "a/dest.txt",
                                              {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 2})
    assert res["result"] == "move_already_applied" and res["linked"] is False


def test_move_rolls_back_on_failure(db, monkeypatch) -> None:
    repo = SourceIndexRepository(db)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")

    def _boom(*a, **k):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(repo, "_mark_deleted_by_source_id_locked", _boom)
    with pytest.raises(RuntimeError):
        repo.apply_confirmed_same_root_move("work", "a/old.txt", "a/new.txt",
                                            {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 2})
    # old entity left current (rolled back)
    assert _row(db, old)[:2] == (0, 1) and _row(db, old)[2] == "LIVE"


# ---------------- R11-D1 provider: old ref → unavailable, never "moved" ----------------

def _env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(
        external_sources=[ExternalSourceRoot(source_root_key="work", path=str(tmp_path))])
    _trust(db, config, "work")
    repo = SourceIndexRepository(db)
    return db, config, repo


def test_find_successor_is_always_none(tmp_path) -> None:
    db, config, repo = _env(tmp_path)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    # even after a move, no successor is ever reported (R11-D1).
    repo.apply_confirmed_same_root_move("work", "a/old.txt", "a/new.txt",
                                        {"file_ext": "txt", "size_bytes": 20, "mtime_ns": 2})
    assert repo.find_successor_source_id(old) is None


def test_deleted_old_ref_is_unavailable_not_moved(tmp_path) -> None:
    db, config, repo = _env(tmp_path)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    legacy = source_id_for("external_file", source_root_key="work", rel_path="a/old.txt")
    repo.mark_deleted("external_file", "a/old.txt")  # P2 tombstone
    # a v2 entity ref for the (now tombstoned) entity: the provider answers unavailable, never "moved".
    r = svc.read_source_file(repo, config, source_ref=encode_source_ref(old), mode="complete")
    assert r["retrieval_state"] == "unavailable"
    assert "successor_source_ref" not in r
    # the legacy handle still resolves to the original tombstoned entity (not a successor).
    assert repo.resolve_entity(source_id=legacy) == old


def test_plain_deleted_without_lineage_is_unavailable(tmp_path) -> None:
    db, config, repo = _env(tmp_path)
    sid = _insert_source(db, root_key="work", rel_path="a/gone.txt")
    repo.mark_deleted("external_file", "a/gone.txt")
    r = svc.read_source_file(repo, config, source_ref=encode_source_ref(sid), mode="complete")
    assert r["retrieval_state"] == "unavailable"


# ---------------- watcher: enqueue-only 'moved' event vs conservative fallback ----------------
# The observer thread NEVER stats/mutates: on_moved enqueues one governed 'moved' event carrying both
# paths, or falls back to delete+create. The readiness-gated drain owns the actual relocation.

def _queued(db: str):
    with sqlite3.connect(db) as c:
        return c.execute("SELECT event_type, rel_path, dest_rel_path, source_root_key "
                         "FROM source_intelligence_events WHERE status='queued' "
                         "ORDER BY event_type").fetchall()


def test_watcher_same_root_move_enqueues_moved_event_no_mutation(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "work"
    (root / "a").mkdir(parents=True)
    old = _insert_source(db, root_key="work", rel_path="a/old.txt")
    repo = SourceIndexRepository(db)
    outcome = source_watch.enqueue_move(repo, "work", root, str(root / "a" / "old.txt"),
                                        str(root / "a" / "new.txt"))
    assert outcome == "moved"
    assert _queued(db) == [("moved", "a/old.txt", "a/new.txt", "work")]
    assert _row(db, old)[:2] == (0, 1)  # old row untouched on the observer thread


def test_watcher_cross_root_move_falls_back_to_delete_create(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "work"
    (root / "a").mkdir(parents=True)
    repo = SourceIndexRepository(db)
    outcome = source_watch.enqueue_move(repo, "work", root, str(root / "a" / "old.txt"),
                                        str(tmp_path / "elsewhere" / "new.txt"))
    assert outcome == "fallback"
    assert _queued(db) == []


def test_watcher_vault_root_move_falls_back(tmp_path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "vault"
    root.mkdir(exist_ok=True)
    repo = SourceIndexRepository(db)
    from hb_assistant.obsidian_mcp.source_indexer import _VAULT_ROOT_KEY  # noqa: PLC0415

    outcome = source_watch.enqueue_move(repo, _VAULT_ROOT_KEY, root, str(root / "old.txt"),
                                        str(root / "new.txt"))
    assert outcome == "fallback"
