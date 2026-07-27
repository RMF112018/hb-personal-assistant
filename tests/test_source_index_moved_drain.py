"""Phase B / B4 corrective — governed 'moved' event drain (PB-005/006/007/010; C4 + C6).

Proves the rename/move mutation runs OFF the observer thread, in the readiness-gated, symlink/identity-safe
drain: a recoverable condition (stale/unready root, lost mount, dest not yet visible, pre/post-mutation
drift, pending re-extraction) DEFERS with bounded backoff and leaves the old row current until the move is
proven safe; a provably-invalid destination is a fail-closed terminal skip that never deletes the old row;
and reindex outcomes are honestly reported (retryable failure, exhaustion -> error, never a false 'done').

Root-trust readiness is stubbed here (``load_root_trust`` is exercised in test_source_root_trust.py) so
these tests isolate the drain disposition matrix.
"""

from __future__ import annotations

import os
import sqlite3
import types
import uuid
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository, source_id_for
from hb_assistant.obsidian_mcp.source_indexer import drain_queue, index_source_file
from hb_assistant.store.migrator import SQLiteMigrator


def _patch_trust(monkeypatch, *, safe: bool) -> None:
    monkeypatch.setattr(
        "hb_assistant.obsidian_mcp.source_root_trust.load_root_trust",
        lambda *a, **k: types.SimpleNamespace(safe_for_watcher_activation=safe),
    )


def _env(tmp_path: Path):
    root = tmp_path / "work"
    root.mkdir()
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    config = ObsidianMcpConfig(
        external_sources=[ExternalSourceRoot(source_root_key="work", path=str(root), enabled=True)]
    )
    repo = SourceIndexRepository(db)
    return db, root, config, repo


def _index_file(root: Path, rel: str, body: str, repo, config) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    sid = index_source_file(p, config.external_sources[0], repo, config)
    assert sid is not None, "precondition: old file indexed"
    return sid


def _resolve_entity(db: str, handle: str) -> str | None:
    """Resolve a durable entity id OR a legacy locator source_id to the entity (DISTINCT). None if
    absent/ambiguous."""
    with sqlite3.connect(db) as c:
        if c.execute("SELECT 1 FROM source_index_entities WHERE source_entity_id=?",
                     (handle,)).fetchone():
            return handle
        rows = c.execute("SELECT DISTINCT source_entity_id FROM source_index_locators WHERE source_id=?",
                         (handle,)).fetchall()
    return rows[0][0] if len(rows) == 1 else None


def _row(db: str, handle: str):
    """(deleted, active, entity_status) for an entity addressed by its durable id or a legacy handle;
    None if the entity does not exist (e.g. a destination the drain has not yet re-indexed)."""
    ent = _resolve_entity(db, handle)
    if ent is None:
        return None
    with sqlite3.connect(db) as c:
        return c.execute(
            "SELECT s.deleted, s.active, e.status FROM source_intelligence_sources s "
            "JOIN source_index_entities e ON e.source_entity_id = s.source_entity_id "
            "WHERE s.source_entity_id=?", (ent,)).fetchone()


def _event(db: str):
    with sqlite3.connect(db) as c:
        return c.execute("SELECT status, error_code, next_attempt_at FROM source_intelligence_events "
                         "ORDER BY created_at DESC LIMIT 1").fetchone()


def _enqueue_move(repo, old_rel: str, new_rel: str):
    repo.enqueue_event(event_type="moved", rel_path=old_rel, dest_rel_path=new_rel,
                       source_root_key="work")


# ---------------- happy path ----------------

def test_ready_root_move_applies(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "a/old.txt", "hello", repo, config)
    (root / "a" / "new.txt").write_text("hello moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="a/new.txt")
    _enqueue_move(repo, "a/old.txt", "a/new.txt")
    drain_queue(repo, config)
    assert _row(db, old)[0] == 1 and _row(db, old)[2] == "TOMBSTONED"   # old P2-tombstoned
    assert _row(db, new)[:2] == (0, 1) and _row(db, new)[2] == "LIVE"   # dest re-indexed: fresh LIVE entity
    assert repo.find_successor_source_id(old) is None                   # R11-D1: no lineage successor
    assert _event(db)[0] == "done"


def test_source_missing_indexes_destination_as_ordinary(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    # No predecessor indexed. A move whose source is unknown indexes the dest as an ordinary current
    # source with NO fabricated lineage.
    (root / "new.txt").write_text("orphan dest")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    _enqueue_move(repo, "missing.txt", "new.txt")
    drain_queue(repo, config)
    assert _row(db, new)[:2] == (0, 1) and _row(db, new)[2] == "LIVE"   # ordinary LIVE entity, no lineage
    assert _event(db)[0] == "done"


# ---------------- recoverable deferrals (never terminally consumed) ----------------

def test_stale_root_defers_then_applies_after_recovery(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    old = _index_file(root, "old.txt", "hi", repo, config)
    (root / "new.txt").write_text("hi moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    _enqueue_move(repo, "old.txt", "new.txt")
    # 1) stale at first drain -> deferred, retryable, old row current, no successor
    _patch_trust(monkeypatch, safe=False)
    drain_queue(repo, config)
    st, code, nxt = _event(db)
    assert st == "queued" and code == "root_not_ready" and nxt is not None
    assert _row(db, old)[0] == 0 and repo.find_successor_source_id(old) is None
    # 2) becomes ready; clear the backoff so the SAME event is eligible -> it applies
    _patch_trust(monkeypatch, safe=True)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET next_attempt_at=NULL")
        c.commit()
    drain_queue(repo, config)
    assert _row(db, old)[0] == 1 and repo.find_successor_source_id(old) is None
    assert _row(db, new)[2] == "LIVE"
    assert _event(db)[0] == "done"


def test_unavailable_mount_defers_not_consumed(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    # old entity present in the index, but the mount is gone at drain time
    legacy = source_id_for("external_file", source_root_key="work", rel_path="old.txt")
    old = uuid.uuid4().hex
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_index_entities(source_entity_id,created_at,status) "
                  "VALUES(?,?, 'LIVE')", (old, "t"))
        c.execute("INSERT INTO source_index_locators(locator_id,source_entity_id,source_id,"
                  "source_root_key,rel_path,is_current_locator,tombstoned_at,generation_seq) "
                  "VALUES(?,?,?,?,?,1,NULL,0)", (uuid.uuid4().hex, old, legacy, "work", "old.txt"))
        c.execute("INSERT INTO source_intelligence_sources(source_entity_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (old, "external_file", "work", "old.txt"))
        c.commit()
    config.external_sources[0].path = str(tmp_path / "gone")  # non-existent root
    _enqueue_move(repo, "old.txt", "new.txt")
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "queued" and code == "root_unavailable"
    assert _row(db, old)[0] == 0  # old row untouched


def test_dest_absent_defers_then_appears(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    _enqueue_move(repo, "old.txt", "new.txt")  # dest not on disk yet
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "queued" and code == "dest_absent" and _row(db, old)[0] == 0
    # dest appears; clear backoff -> applies
    (root / "new.txt").write_text("x moved")
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET next_attempt_at=NULL")
        c.commit()
    drain_queue(repo, config)
    assert _row(db, old)[0] == 1 and _event(db)[0] == "done"


# ---------------- terminal, fail-closed (never delete old) ----------------

def test_symlink_destination_is_terminal_and_keeps_old_current(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    outside = tmp_path / "outside.txt"
    outside.write_text("evil")
    os.symlink(outside, root / "new.txt")  # symlink destination
    _enqueue_move(repo, "old.txt", "new.txt")
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "skipped" and code == "dest_not_regular"
    assert _row(db, old)[0] == 0  # old row NOT deleted by a symlink dest
    assert repo.find_successor_source_id(old) is None


# ---------------- dedup on both paths ----------------

def test_distinct_move_destinations_not_deduplicated(tmp_path) -> None:
    db, root, config, repo = _env(tmp_path)
    _enqueue_move(repo, "a.txt", "b.txt")
    _enqueue_move(repo, "a.txt", "c.txt")   # different dest -> distinct event
    _enqueue_move(repo, "a.txt", "b.txt")   # identical -> coalesced
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT dest_rel_path FROM source_intelligence_events "
                         "WHERE event_type='moved' AND status='queued' ORDER BY dest_rel_path").fetchall()
    assert [r[0] for r in rows] == ["b.txt", "c.txt"]


# ---------------- reindex failure recovery + honest exhaustion ----------------

def test_reindex_failure_is_retryable_then_succeeds(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    _enqueue_move(repo, "old.txt", "new.txt")
    # 1) R11-D3: the source-side P2 tombstone commits; the destination P1 is the drain's re-index. With
    #    re-index -> None the destination is NOT yet created (pending = not indexed), event retryable.
    monkeypatch.setattr(si, "index_source_file", lambda *a, **k: None)
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "queued" and code == "dest_reindex_pending"
    assert _row(db, old)[0] == 1 and _row(db, old)[2] == "TOMBSTONED"   # source side committed
    assert _row(db, new) is None                                        # destination not yet indexed
    # 2) reindex recovers on retry -> destination P1 established -> done; no lineage carried
    monkeypatch.undo()
    _patch_trust(monkeypatch, safe=True)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET next_attempt_at=NULL")
        c.commit()
    drain_queue(repo, config)
    assert _event(db)[0] == "done"
    assert _row(db, new)[2] == "LIVE" and repo.find_successor_source_id(old) is None


def test_reindex_exhaustion_is_error_not_done(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    _enqueue_move(repo, "old.txt", "new.txt")
    monkeypatch.setattr(si, "index_source_file", lambda *a, **k: None)  # always fails
    # Drive the event past MOVED_MAX_ATTEMPTS claim cycles (clearing backoff each time).
    for _ in range(10):
        with sqlite3.connect(db) as c:
            c.execute("UPDATE source_intelligence_events SET next_attempt_at=NULL WHERE status='queued'")
            c.commit()
        drain_queue(repo, config)
        if _event(db)[0] != "queued":
            break
    st, code, _ = _event(db)
    assert st == "error" and code == "dest_reindex_exhausted"
    # trust-critical invariants: source side committed (TOMBSTONED); destination never created/advertised
    assert _row(db, old)[0] == 1 and _row(db, old)[2] == "TOMBSTONED" and _row(db, new) is None


# ---------------- pre/post-transaction resolved-path/identity drift ----------------

def _drift_resolver(seq):
    """Return a resolve_destination stub yielding 'contained' with a per-call identity from ``seq``
    (resolved_path fixed) so only identity drives the drift decision."""
    calls = {"n": 0}

    def _res(root_path, new_rel):
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return si.DestinationResolution("contained", resolved_path=Path("/x"),
                                        identity=(0, 0, int(seq[i]), 0))

    return _res


def test_pre_transaction_drift_keeps_old_current(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    _enqueue_move(repo, "old.txt", "new.txt")
    # call 1 (resolve) vs call 2 (pre-txn) differ → drift BEFORE the move → no mutation.
    monkeypatch.setattr(si, "resolve_destination", _drift_resolver([1, 2]))
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "queued" and code == "dest_changed_before_move"
    assert _row(db, old)[0] == 0 and repo.find_successor_source_id(old) is None  # NOT mutated


def test_post_transaction_drift_leaves_old_superseded(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    _enqueue_move(repo, "old.txt", "new.txt")
    # calls 1 (resolve) & 2 (pre-txn) match → move proceeds; call 3 (post-txn) differs → drift AFTER move.
    monkeypatch.setattr(si, "resolve_destination", _drift_resolver([7, 7, 8]))
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "queued" and code == "dest_changed_during_move"
    # source side already committed (TOMBSTONED, not restored); post-move drift defers BEFORE the
    # destination re-index, so the destination is not yet created (never advertised complete).
    assert _row(db, old)[0] == 1 and _row(db, old)[2] == "TOMBSTONED"
    assert _row(db, new) is None


# ---------------- queue safety ----------------

def test_defer_conflict_when_event_not_processing(tmp_path) -> None:
    db, root, config, repo = _env(tmp_path)
    eid = repo.enqueue_event(event_type="moved", rel_path="a.txt", dest_rel_path="b.txt",
                             source_root_key="work")
    # event is 'queued', not 'processing' -> defer must fail closed
    assert repo.defer_event(eid, error_code="x", expected_attempt=1) == "conflict"


def test_moved_invalid_payload_is_terminal(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    repo.enqueue_event(event_type="moved", rel_path="a.txt", dest_rel_path="a.txt",
                       source_root_key="work")  # old == new
    drain_queue(repo, config)
    assert _event(db)[:2] == ("skipped", "moved_invalid")


# ---------------- PB-006: canonical validation of BOTH paths + resolved containment ----------------

@pytest.mark.parametrize("old_rel,new_rel", [
    ("/abs/old.txt", "new.txt"),        # absolute predecessor
    ("../old.txt", "new.txt"),          # traversal predecessor
    ("a\\old.txt", "new.txt"),          # backslash predecessor
    ("a//old.txt", "new.txt"),          # duplicate separators
    (".hidden/old.txt", "new.txt"),     # protected/hidden predecessor
    ("old.txt", "/abs/new.txt"),        # absolute destination (must NEVER be probed)
    ("old.txt", "../new.txt"),          # traversal destination
])
def test_invalid_paths_are_terminal_no_mutation(tmp_path, monkeypatch, old_rel, new_rel) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    # index a predecessor at the *canonical* old path so we can prove it is never mutated
    canon_old = _index_file(root, "old.txt", "x", repo, config)
    # resolve_destination is the ONLY destination filesystem probe; lexical validation rejects an
    # absolute/traversal path first, so it must never be reached (no FS probe of an escape).
    monkeypatch.setattr(si, "resolve_destination",
                        lambda *a, **k: pytest.fail("filesystem probed for an invalid path"))
    repo.enqueue_event(event_type="moved", rel_path=old_rel, dest_rel_path=new_rel,
                       source_root_key="work")
    drain_queue(repo, config)
    assert _event(db)[:2] == ("skipped", "moved_invalid")
    assert _row(db, canon_old)[0] == 0  # canonical predecessor untouched


def test_parent_symlink_escape_rejected_before_mutation(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    # a regular file OUTSIDE the root, reached via a symlinked PARENT dir inside the root
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_text("SECRET OUTSIDE CONTENT")
    os.symlink(outside, root / "linked")           # root/linked -> /outside (parent symlink)
    _enqueue_move(repo, "old.txt", "linked/f.txt")  # lstat sees a regular file (parent traversed)
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "skipped" and code == "dest_escapes_root"  # resolved-path containment catches it
    assert _row(db, old)[0] == 0                    # old NOT superseded
    # outside content was never indexed under this root
    outside_sid = source_id_for("external_file", source_root_key="work", rel_path="linked/f.txt")
    assert _row(db, outside_sid) is None


# ---------------- PB-010: stale claim generation cannot mutate / index / complete ----------------

def test_stale_claim_cannot_complete_or_defer(tmp_path) -> None:
    db, root, config, repo = _env(tmp_path)
    eid = repo.enqueue_event(event_type="moved", rel_path="a.txt", dest_rel_path="b.txt",
                             source_root_key="work")
    repo.claim_queued(50)                      # attempt 1 (status=processing, attempts=1)
    # simulate stuck-reclaim: back to queued, then a second claim → attempt 2
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET status='queued' WHERE event_id=?", (eid,))
        c.commit()
    repo.claim_queued(50)                      # attempt 2 now owns it
    # stale worker A (expected_attempt=1) cannot defer or complete the reclaimed event
    assert repo.defer_event(eid, error_code="x", expected_attempt=1) == "conflict"
    assert repo.complete_owned_event(eid, "done", expected_attempt=1) == "conflict"
    assert repo.heartbeat_owned_event(eid, expected_attempt=1) == "conflict"  # stale gen cannot refresh
    assert repo.event_is_owned(eid, 1) is False and repo.event_is_owned(eid, 2) is True
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status, attempts FROM source_intelligence_events "
                         "WHERE event_id=?", (eid,)).fetchone() == ("processing", 2)  # attempt 2 intact


def test_stale_claim_move_is_claim_conflict_no_mutation(tmp_path) -> None:
    db, root, config, repo = _env(tmp_path)
    old = _index_file(root, "old.txt", "x", repo, config)
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")
    repo.claim_queued(50)  # attempt 1
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET status='queued' WHERE event_id=?", (eid,))
        c.commit()
    repo.claim_queued(50)  # attempt 2 owns it
    # a stale attempt-1 move must NOT mutate source/lineage
    res = repo.apply_owned_confirmed_same_root_move(
        event_id=eid, expected_attempt=1, root_key="work",
        old_relative_path="old.txt", new_relative_path="new.txt",
        destination_metadata={"file_ext": "txt", "size_bytes": 1, "mtime_ns": 1})
    assert res["result"] == "claim_conflict"
    assert _row(db, old)[0] == 0 and repo.find_successor_source_id(old) is None  # untouched


# ---------------- PB-010 (C4): atomic write-lock ownership, busy fail-closed, lease refresh ----------------

def test_concurrent_reclaim_cannot_race_owned_move(tmp_path, monkeypatch) -> None:
    """The guarded ownership UPDATE takes the write lock as its FIRST statement, so at the mutation boundary
    a second connection provably cannot reclaim (BUSY/LOCKED) until this move commits. Proves the
    'A's guard succeeds before B' ordering — B cannot slip a reclaim between ownership and mutation."""
    db, root, config, repo = _env(tmp_path)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")
    repo.claim_queued(50)  # attempt 1 (processing, attempts=1)
    outcome: dict = {}
    orig = repo._confirmed_move_locked
    b = sqlite3.connect(db, timeout=0)
    b.execute("PRAGMA busy_timeout=0")
    try:
        def spy(c, *a, **k):
            # Worker A has executed the guarded ownership UPDATE and now holds the RESERVED write lock.
            try:
                b.execute("BEGIN IMMEDIATE")  # a concurrent reclaim tries to acquire the write lock
                b.execute("UPDATE source_intelligence_events SET status='queued', attempts=attempts+1 "
                          "WHERE event_id=?", (eid,))
                b.commit()
                outcome["reclaimed"] = True
            except sqlite3.OperationalError as e:
                outcome["busy"] = (getattr(e, "sqlite_errorcode", 0) or 0) & 0xFF
                b.rollback()
            return orig(c, *a, **k)
        monkeypatch.setattr(repo, "_confirmed_move_locked", spy)
        res = repo.apply_owned_confirmed_same_root_move(
            event_id=eid, expected_attempt=1, root_key="work",
            old_relative_path="old.txt", new_relative_path="new.txt",
            destination_metadata={"file_ext": "txt", "size_bytes": 1, "mtime_ns": 1})
    finally:
        b.rollback()
        b.close()
    assert outcome.get("busy") in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)  # B blocked at the boundary
    assert "reclaimed" not in outcome                                          # B never reclaimed under A
    assert res["result"] == "move_applied"
    # the legitimate owner P2-tombstoned old (source side); the destination P1 is the drain's separate
    # re-index (not performed by this direct owned-move call).
    assert _row(db, old)[0] == 1 and _row(db, old)[2] == "TOMBSTONED" and _row(db, new) is None


def test_reclaim_after_move_blocks_stale_indexing(tmp_path, monkeypatch) -> None:
    """A reclaim that commits AFTER the move but BEFORE indexing is caught by the pre-index heartbeat
    (conflict) → the stale claim does NOT index the destination."""
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")
    calls = {"index": 0}
    monkeypatch.setattr(si, "index_source_file",
                        lambda *a, **k: calls.__setitem__("index", calls["index"] + 1))
    orig = repo.apply_owned_confirmed_same_root_move

    def wrap(**kw):
        res = orig(**kw)  # the move commits here
        # a concurrent worker reclaims the event (attempts 1 -> 2) before this drain reaches the heartbeat
        with sqlite3.connect(db) as c:
            c.execute("UPDATE source_intelligence_events SET status='queued' WHERE event_id=?", (kw["event_id"],))
            c.commit()
        repo.claim_queued(50)  # attempt 2 now owns it
        return res

    monkeypatch.setattr(repo, "apply_owned_confirmed_same_root_move", wrap)
    drain_queue(repo, config)
    assert calls["index"] == 0                                # stale attempt-1 never indexed
    # source side committed (TOMBSTONED); the reclaim blocked indexing so the destination is not created.
    assert _row(db, old)[0] == 1 and _row(db, old)[2] == "TOMBSTONED" and _row(db, new) is None
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status, attempts FROM source_intelligence_events WHERE event_id=?",
                         (eid,)).fetchone() == ("processing", 2)  # current owner (attempt 2) untouched


def test_db_busy_through_defer_is_recoverable(tmp_path, monkeypatch) -> None:
    """An unrelated writer holding the DB write lock through BOTH the move ownership attempt AND the
    deferral → no mutation, no terminal transition, event stays recoverable; after release + deterministic
    stuck recovery the move completes."""
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    new = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")
    repo.claim_queued(50)  # attempt 1
    a = sqlite3.connect(db, timeout=0)  # worker A: no busy wait
    a.execute("PRAGMA busy_timeout=0")
    b = sqlite3.connect(db, timeout=0)  # unrelated writer B
    b.execute("PRAGMA busy_timeout=0")
    b.execute("BEGIN IMMEDIATE")  # B holds the write lock
    try:
        move = repo.apply_owned_confirmed_same_root_move(
            event_id=eid, expected_attempt=1, root_key="work",
            old_relative_path="old.txt", new_relative_path="new.txt",
            destination_metadata={"file_ext": "txt", "size_bytes": 1, "mtime_ns": 1}, conn=a)
        assert move["result"] == "db_busy"                                    # no lock acquired, no mutation
        assert repo.defer_event(eid, error_code="db_busy", expected_attempt=1, conn=a) == "db_busy"
    finally:
        b.rollback()
        b.close()
        a.rollback()
        a.close()
    assert _row(db, old)[0] == 0 and repo.find_successor_source_id(old) is None  # nothing mutated
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status, attempts FROM source_intelligence_events WHERE event_id=?",
                         (eid,)).fetchone() == ("processing", 1)  # recoverable, not terminal
        # deterministic stuck recovery: seed an old lease so requeue_stuck is eligible (no wall-clock wait)
        c.execute("UPDATE source_intelligence_events SET updated_at='2000-01-01T00:00:00+00:00' "
                  "WHERE event_id=?", (eid,))
        c.commit()
    assert repo.requeue_stuck(900) == 1
    drain_queue(repo, config)                                     # attempt 2 claims + completes the move
    assert _event(db)[0] == "done"
    assert _row(db, old)[0] == 1 and _row(db, new)[2] == "LIVE"   # source tombstoned; dest re-indexed


def test_db_busy_during_terminal_completion_is_recoverable(tmp_path) -> None:
    """Exhaustion followed by a CONTENDED terminal write: defer returns 'exhausted', then the guarded
    terminal completion hits BUSY → 'db_busy', leaving the event 'processing' (never a false terminal);
    after release the terminal completion persists."""
    db, root, config, repo = _env(tmp_path)
    eid = repo.enqueue_event(event_type="moved", rel_path="a.txt", dest_rel_path="b.txt",
                             source_root_key="work")
    repo.claim_queued(50)  # attempt 1
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET attempts=6 WHERE event_id=?", (eid,))
        c.commit()
    # at the exhaustion boundary defer_event does NO write and reports 'exhausted'
    assert repo.defer_event(eid, error_code="dest_reindex_pending", expected_attempt=6) == "exhausted"
    a = sqlite3.connect(db, timeout=0)
    a.execute("PRAGMA busy_timeout=0")
    b = sqlite3.connect(db, timeout=0)
    b.execute("PRAGMA busy_timeout=0")
    b.execute("BEGIN IMMEDIATE")  # contention on the terminal write
    try:
        assert repo.complete_owned_event(
            eid, "error", expected_attempt=6, error_code="dest_reindex_exhausted", conn=a) == "db_busy"
    finally:
        b.rollback()
        b.close()
        a.rollback()
        a.close()
    with sqlite3.connect(db) as c:  # left processing (recoverable), NOT terminal
        assert c.execute("SELECT status, attempts FROM source_intelligence_events WHERE event_id=?",
                         (eid,)).fetchone() == ("processing", 6)
    # after release, the guarded terminal completion persists
    assert repo.complete_owned_event(
        eid, "error", expected_attempt=6, error_code="dest_reindex_exhausted") == "completed"
    assert _event(db)[:2] == ("error", "dest_reindex_exhausted")


def test_non_busy_operational_error_is_terminal_error(tmp_path, monkeypatch) -> None:
    """A NON-busy OperationalError in the moved handler surfaces as a terminal 'error' (not silently
    retained/retried)."""
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    _enqueue_move(repo, "old.txt", "new.txt")

    def boom(**kw):
        raise sqlite3.OperationalError("no such column: bogus")  # NOT busy/locked

    monkeypatch.setattr(repo, "apply_owned_confirmed_same_root_move", boom)
    drain_queue(repo, config)
    assert _event(db)[:2] == ("error", "OperationalError")


def test_busy_raised_in_moved_handler_leaves_processing(tmp_path, monkeypatch) -> None:
    """A BUSY/LOCKED OperationalError raised in the moved handler is retryable: the event is left
    'processing' for requeue_stuck (fail-closed), never a false terminal. Also exercises the message
    fallback of is_sqlite_busy (a fabricated error carries no numeric code)."""
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")

    def boom(**kw):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(repo, "apply_owned_confirmed_same_root_move", boom)
    drain_queue(repo, config)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status FROM source_intelligence_events WHERE event_id=?",
                         (eid,)).fetchone()[0] == "processing"


def test_is_sqlite_busy_classifies_primary_and_extended() -> None:
    """The classifier masks EXTENDED result codes to the primary code and rejects unrelated errors."""
    from hb_assistant.obsidian_mcp.source_index_repository import is_sqlite_busy

    class _E:  # stand-in carrying a numeric sqlite_errorcode
        def __init__(self, code: int) -> None:
            self.sqlite_errorcode = code

    assert is_sqlite_busy(_E(sqlite3.SQLITE_BUSY)) is True                 # primary busy (5)
    assert is_sqlite_busy(_E(sqlite3.SQLITE_LOCKED)) is True               # primary locked (6)
    assert is_sqlite_busy(_E(sqlite3.SQLITE_BUSY | (1 << 8))) is True      # extended busy (e.g. 261)
    assert is_sqlite_busy(_E(sqlite3.SQLITE_LOCKED | (2 << 8))) is True    # extended locked
    assert is_sqlite_busy(_E(1)) is False                                 # SQLITE_ERROR — not busy
    # no numeric code -> narrow message fallback (only for OperationalError)
    assert is_sqlite_busy(sqlite3.OperationalError("database is locked")) is True
    assert is_sqlite_busy(sqlite3.OperationalError("no such table: x")) is False
    assert is_sqlite_busy(ValueError("locked")) is False                  # not OperationalError, no code


def test_move_and_heartbeat_refresh_lease_to_controlled_timestamp(tmp_path, monkeypatch) -> None:
    """The move-boundary guarded UPDATE and the pre-index heartbeat each refresh the lease to the injected
    timestamp (controlled clock — no 'two fast stamps differ' race); a stale generation cannot refresh."""
    import hb_assistant.obsidian_mcp.source_index_repository as R
    db, root, config, repo = _env(tmp_path)
    _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")
    repo.claim_queued(50)  # attempt 1

    def _uat() -> str:
        with sqlite3.connect(db) as c:
            return c.execute("SELECT updated_at FROM source_intelligence_events WHERE event_id=?",
                             (eid,)).fetchone()[0]

    monkeypatch.setattr(R, "_now", lambda: "2030-01-02T03:04:05+00:00")
    move = repo.apply_owned_confirmed_same_root_move(
        event_id=eid, expected_attempt=1, root_key="work",
        old_relative_path="old.txt", new_relative_path="new.txt",
        destination_metadata={"file_ext": "txt", "size_bytes": 1, "mtime_ns": 1})
    assert move["result"] == "move_applied"
    assert _uat() == "2030-01-02T03:04:05+00:00"                 # move boundary refreshed the lease

    monkeypatch.setattr(R, "_now", lambda: "2031-06-07T08:09:10+00:00")
    assert repo.heartbeat_owned_event(eid, expected_attempt=1) == "ok"
    assert _uat() == "2031-06-07T08:09:10+00:00"                 # heartbeat refreshed it again

    monkeypatch.setattr(R, "_now", lambda: "2099-12-31T00:00:00+00:00")
    assert repo.heartbeat_owned_event(eid, expected_attempt=2) == "conflict"  # wrong generation
    assert _uat() == "2031-06-07T08:09:10+00:00"                 # stale gen did NOT refresh


# ---------------- PB-010 (C6/C8): no moved event reaches the generic unguarded complete_event fallback;
# ---------------- the claim generation is validated at the dispatch entry (no fabricated attempt) ----------------

def _spy(store: list):
    def _fn(*a, **k):
        store.append((a, k))
    return _fn


def test_moved_guarded_terminal_failure_never_reaches_unguarded_fallback(tmp_path, monkeypatch) -> None:
    """Full escape sequence: attempt 1 processes, a concurrent reclaim bumps to attempt 2, the move raises
    non-busy, the inner guarded terminalization raises non-busy, and the generic backstop retries the
    GUARDED completion (attempt 1) — the unguarded complete_event() is NEVER used and attempt 2 stays
    authoritative."""
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")

    ce_calls: list = []
    monkeypatch.setattr(repo, "complete_event", _spy(ce_calls))
    coe_attempts: list = []

    def _raise_coe(event_id, status, *, expected_attempt, error_code=None, conn=None):
        coe_attempts.append(expected_attempt)
        raise sqlite3.OperationalError("no such column: bogus")  # NON-busy

    monkeypatch.setattr(repo, "complete_owned_event", _raise_coe)

    def wrap(**kw):
        # attempt 1 is mid-flight; a concurrent worker reclaims to attempt 2, then this move raises non-busy
        with sqlite3.connect(db) as c:
            c.execute("UPDATE source_intelligence_events SET status='queued' WHERE event_id=?",
                      (kw["event_id"],))
            c.commit()
        repo.claim_queued(50)  # attempt 2 now owns it
        raise sqlite3.OperationalError("no such table: bogus")  # NON-busy

    monkeypatch.setattr(repo, "apply_owned_confirmed_same_root_move", wrap)

    drain_queue(repo, config)  # must NOT raise

    assert len(coe_attempts) >= 2                       # inner handler + generic backstop both reached
    assert all(a == 1 for a in coe_attempts) and 2 not in coe_attempts  # stale attempt only; never attempt 2
    assert ce_calls == []                               # unguarded fallback never used for the moved event
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status, attempts FROM source_intelligence_events WHERE event_id=?",
                         (eid,)).fetchone() == ("processing", 2)  # attempt 2 authoritative
    assert _row(db, old)[0] == 0 and repo.find_successor_source_id(old) is None  # stale attempt mutated nothing
    # recoverable via deterministic stuck recovery (restore real methods first)
    monkeypatch.undo()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET updated_at='2000-01-01T00:00:00+00:00' "
                  "WHERE event_id=?", (eid,))
        c.commit()
    assert repo.requeue_stuck(900) == 1


def test_moved_invalid_terminalization_failure_reaches_backstop(tmp_path, monkeypatch) -> None:
    """The `moved_invalid` branch's guarded terminalization raises non-busy → the generic backstop catches
    it (guarded retry), never the unguarded fallback."""
    db, root, config, repo = _env(tmp_path)
    ce_calls: list = []
    monkeypatch.setattr(repo, "complete_event", _spy(ce_calls))
    coe_attempts: list = []

    def _raise_coe(event_id, status, *, expected_attempt, error_code=None, conn=None):
        coe_attempts.append(expected_attempt)
        raise sqlite3.OperationalError("no such column: bogus")

    monkeypatch.setattr(repo, "complete_owned_event", _raise_coe)
    eid = repo.enqueue_event(event_type="moved", rel_path="a.txt", dest_rel_path="a.txt",  # old == new
                             source_root_key="work")
    drain_queue(repo, config)  # must NOT raise
    assert len(coe_attempts) >= 2 and all(a == 1 for a in coe_attempts)  # branch + backstop, claimed attempt
    assert ce_calls == []
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status FROM source_intelligence_events WHERE event_id=?",
                         (eid,)).fetchone()[0] == "processing"
    monkeypatch.undo()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET updated_at='2000-01-01T00:00:00+00:00' "
                  "WHERE event_id=?", (eid,))
        c.commit()
    assert repo.requeue_stuck(900) == 1


def test_unconfigured_moved_terminalization_failure_reaches_backstop(tmp_path, monkeypatch) -> None:
    """The `unconfigured_root` branch's guarded terminalization raises non-busy → the generic backstop
    catches it (guarded retry), never the unguarded fallback."""
    db, root, config, repo = _env(tmp_path)
    ce_calls: list = []
    monkeypatch.setattr(repo, "complete_event", _spy(ce_calls))
    coe_attempts: list = []

    def _raise_coe(event_id, status, *, expected_attempt, error_code=None, conn=None):
        coe_attempts.append(expected_attempt)
        raise sqlite3.OperationalError("no such column: bogus")

    monkeypatch.setattr(repo, "complete_owned_event", _raise_coe)
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="ghost")  # not a configured root
    drain_queue(repo, config)  # must NOT raise
    assert len(coe_attempts) >= 2 and all(a == 1 for a in coe_attempts)
    assert ce_calls == []
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status FROM source_intelligence_events WHERE event_id=?",
                         (eid,)).fetchone()[0] == "processing"
    monkeypatch.undo()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET updated_at='2000-01-01T00:00:00+00:00' "
                  "WHERE event_id=?", (eid,))
        c.commit()
    assert repo.requeue_stuck(900) == 1


_INVALID_ATTEMPTS = [
    pytest.param("__MISSING__", id="missing"),
    pytest.param(None, id="none"),
    pytest.param(0, id="zero"),
    pytest.param(-3, id="negative"),
    pytest.param("x", id="nonnumeric"),
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
]


def _event_row(db: str, eid: str):
    """Full moved-event queue row (every field a dispatch/terminalization could touch)."""
    with sqlite3.connect(db) as c:
        return c.execute(
            "SELECT status, attempts, error_code, updated_at, next_attempt_at "
            "FROM source_intelligence_events WHERE event_id=?", (eid,)).fetchone()


@pytest.mark.parametrize("dispatch", ["valid_configured", "moved_invalid", "unconfigured_root"])
@pytest.mark.parametrize("bad_attempt", _INVALID_ATTEMPTS)
def test_moved_dispatch_invalid_claim_generation_no_mutation(
    tmp_path, monkeypatch, dispatch, bad_attempt
) -> None:
    """An invalid claim generation is rejected at the moved DISPATCH ENTRY — before normalization, root
    lookup, dispatch, or any terminalization — for EVERY dispatch class (valid_configured / moved_invalid /
    unconfigured_root) and EVERY invalid form (missing/None/0/negative/string/True/False). No fabricated
    attempt, no post-claim queue mutation, no source/lineage/content/indexing change, deterministic recovery."""
    db, root, config, repo = _env(tmp_path)
    old = _index_file(root, "old.txt", "x", repo, config)  # a real pre-indexed source to prove non-mutation
    (root / "new.txt").write_text("x moved")
    if dispatch == "moved_invalid":
        rel, dest, srk = "old.txt", "old.txt", "work"        # old == new
    elif dispatch == "unconfigured_root":
        rel, dest, srk = "old.txt", "new.txt", "ghost"       # not a configured root
    else:
        rel, dest, srk = "old.txt", "new.txt", "work"        # would otherwise reach _apply_moved_event
    eid = repo.enqueue_event(event_type="moved", rel_path=rel, dest_rel_path=dest, source_root_key=srk)
    repo.claim_queued(50)  # legitimate claim -> processing, attempts=1
    before = _event_row(db, eid)  # snapshot AFTER the legitimate claim, BEFORE the crafted event
    old_before = _row(db, old)

    event = {"event_id": eid, "event_type": "moved", "rel_path": rel, "dest_rel_path": dest,
             "source_root_key": srk, "source_id": None}
    if bad_attempt != "__MISSING__":
        event["attempts"] = bad_attempt
    monkeypatch.setattr(repo, "claim_queued", lambda *a, **k: [event])
    apply_calls: list = []
    coe_calls: list = []
    ce_calls: list = []
    monkeypatch.setattr(si, "_apply_moved_event", _spy(apply_calls))
    monkeypatch.setattr(repo, "complete_owned_event", _spy(coe_calls))
    monkeypatch.setattr(repo, "complete_event", _spy(ce_calls))

    drain_queue(repo, config)  # must NOT raise

    # short-circuit at dispatch entry: no dispatch, no terminalization of any kind
    assert apply_calls == [] and coe_calls == [] and ce_calls == []
    # NO post-claim queue mutation — the FULL event row is byte-identical to the post-claim snapshot
    assert _event_row(db, eid) == before
    # source + lineage + destination content untouched (esp. the valid_configured route that would move/index)
    assert _row(db, old) == old_before and repo.find_successor_source_id(old) is None
    new_sid = source_id_for("external_file", source_root_key="work", rel_path="new.txt")
    assert _row(db, new_sid) is None  # destination never indexed; no content invalidation created
    # recoverable via deterministic stuck recovery
    monkeypatch.undo()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET updated_at='2000-01-01T00:00:00+00:00' "
                  "WHERE event_id=?", (eid,))
        c.commit()
    assert repo.requeue_stuck(900) == 1


def test_terminalize_moved_exception_validates_generation(tmp_path, monkeypatch) -> None:
    """Direct coverage of the defensive backstop helper (independent last-resort boundary): an invalid
    generation calls no guarded completion (no fabricated attempt); a valid generation calls the guarded
    completion and swallows its failure."""
    _, _, _, repo = _env(tmp_path)
    exc = sqlite3.OperationalError("boom")
    for bad in ("__MISSING__", None, 0, -1, "x", True, False):
        coe_calls: list = []
        monkeypatch.setattr(repo, "complete_owned_event", _spy(coe_calls))
        event = {"event_id": "e1"}
        if bad != "__MISSING__":
            event["attempts"] = bad
        si._terminalize_moved_exception(repo, event, exc)
        assert coe_calls == []  # invalid generation → no guarded completion, no fabricated attempt

    # valid generation whose guarded completion RAISES non-busy → swallowed (event left processing)
    seen: list = []

    def _raise_coe(event_id, status, *, expected_attempt, error_code=None, conn=None):
        seen.append(expected_attempt)
        raise sqlite3.OperationalError("no such column")

    monkeypatch.setattr(repo, "complete_owned_event", _raise_coe)
    si._terminalize_moved_exception(repo, {"event_id": "e1", "attempts": 3}, exc)  # must NOT raise
    assert seen == [3]

    # valid generation whose guarded completion SUCCEEDS → called cleanly with that attempt
    ok: list = []

    def _ok_coe(event_id, status, *, expected_attempt, error_code=None, conn=None):
        ok.append(expected_attempt)
        return "completed"

    monkeypatch.setattr(repo, "complete_owned_event", _ok_coe)
    si._terminalize_moved_exception(repo, {"event_id": "e1", "attempts": 2}, exc)
    assert ok == [2]


# ---------------- PB-007: two-stage FTS + public-search invalidation through the drain ----------------

OLD_TOKEN = "zqxoldtoken7141"   # unique tokens that cannot match a path / filename / project metadata
NEW_TOKEN = "zqxnewtoken9273"


def _seed_indexed_destination(db: str, rel: str, token: str) -> str:
    """Give ``rel`` a REAL pre-existing indexed content representation (entity + current locator +
    metadata + text + FTS row) whose excerpt contains ``token``, so it is discoverable via public search
    before a move overwrites it. Returns the durable source_entity_id."""
    legacy = source_id_for("external_file", source_root_key="work", rel_path=rel)
    eid = uuid.uuid4().hex
    with sqlite3.connect(db) as c:
        c.execute("INSERT OR REPLACE INTO source_intelligence_state(state_key,state_value,updated_at) "
                  "VALUES('fts_available','1','t')")
        c.execute("INSERT INTO source_intelligence_fts(text_excerpt, rel_path, aux) VALUES(?,?,?)",
                  (token, rel, ""))
        rowid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("INSERT INTO source_index_entities(source_entity_id,created_at,status) "
                  "VALUES(?,?, 'LIVE')", (eid, "t"))
        c.execute("INSERT INTO source_index_locators(locator_id,source_entity_id,source_id,"
                  "source_root_key,rel_path,is_current_locator,tombstoned_at,generation_seq) "
                  "VALUES(?,?,?,?,?,1,NULL,0)", (uuid.uuid4().hex, eid, legacy, "work", rel))
        c.execute("INSERT INTO source_intelligence_sources(source_entity_id,source_kind,source_root_key,"
                  "rel_path,active,deleted,created_at,updated_at) VALUES(?,?,?,?,1,0,'t','t')",
                  (eid, "external_file", "work", rel))
        c.execute("INSERT INTO source_intelligence_metadata(source_entity_id,file_ext,size_bytes,"
                  "mtime_ns,content_sha256,extraction_status,fts_rowid,indexed_at,extraction_disposition,"
                  "content_indexed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (eid, "txt", 5, 5, "OLDH", "ok", rowid, "t", "content", "t"))
        c.execute("INSERT INTO source_intelligence_text(source_entity_id,text_excerpt,excerpt_char_count,"
                  "excerpt_truncated,full_text_sha256,raw_body_persisted,redaction_applied,updated_at) "
                  "VALUES(?,?,?,?,?,0,1,'t')", (eid, token, len(token), 0, "fsha"))
        c.commit()
    return eid


def test_move_onto_occupied_destination_is_conservative_conflict(tmp_path, monkeypatch) -> None:
    # R11-D3 case 2: old is still current AND the destination is already occupied by a LIVE entity. This
    # is a CONSERVATIVE CONFLICT — the move performs NO mutation (fail closed), the drain terminal-skips
    # (`conflicting_successor`), the old entity stays current, and the destination's existing content is
    # untouched. R11 never overwrites an occupied destination via a degraded move.
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    dest_rel = "dest.txt"
    dest_sid = _seed_indexed_destination(db, dest_rel, OLD_TOKEN)
    (root / dest_rel).write_text(f"{NEW_TOKEN} replacement body")
    assert [r["source_id"] for r in repo.search_source_files(OLD_TOKEN)] == [dest_sid]

    _enqueue_move(repo, "old.txt", dest_rel)
    drain_queue(repo, config)
    assert _event(db)[:2] == ("skipped", "conflicting_successor")
    # NO mutation: old stays current, destination keeps its OLD_TOKEN content, NEW_TOKEN not indexed.
    assert _row(db, old)[:2] == (0, 1) and _row(db, old)[2] == "LIVE"
    assert _row(db, dest_sid)[:2] == (0, 1) and _row(db, dest_sid)[2] == "LIVE"
    assert [r["source_id"] for r in repo.search_source_files(OLD_TOKEN)] == [dest_sid]
    assert repo.search_source_files(NEW_TOKEN) == []
    assert repo.find_successor_source_id(old) is None


def test_unexpected_moved_exception_cannot_overwrite_current_claim(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    eid = repo.enqueue_event(event_type="moved", rel_path="old.txt", dest_rel_path="new.txt",
                             source_root_key="work")

    # force an unexpected error inside the moved handler AFTER claim; the guarded except must complete
    # via the OWNED path (expected_attempt), never the drain's generic unguarded complete_event.
    def _boom(*a, **k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(si, "resolve_destination", _boom)
    # reclaim as a different generation first so the stale expected_attempt cannot win
    repo.claim_queued(50)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET status='queued' WHERE event_id=?", (eid,))
        c.commit()
    # drain claims attempt 2 and hits the exception → guarded error completion on attempt 2
    drain_queue(repo, config)
    with sqlite3.connect(db) as c:
        st, code, att = c.execute("SELECT status, error_code, attempts FROM source_intelligence_events "
                                  "WHERE event_id=?", (eid,)).fetchone()
    assert st == "error" and code == "RuntimeError" and att == 2
