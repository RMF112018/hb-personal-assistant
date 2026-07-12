"""Phase B / B4 corrective — governed 'moved' event drain (PB-005/006/007).

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
from pathlib import Path

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


def _row(db: str, sid: str):
    with sqlite3.connect(db) as c:
        return c.execute("SELECT deleted, active, renamed_from_source_id FROM "
                         "source_intelligence_sources WHERE source_id=?", (sid,)).fetchone()


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
    assert _row(db, old)[0] == 1                     # old superseded
    assert _row(db, new)[:2] == (0, 1) and _row(db, new)[2] == old   # dest current + lineage
    assert repo.find_successor_source_id(old) == new
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
    assert _row(db, new)[:2] == (0, 1) and _row(db, new)[2] is None   # ordinary, no lineage
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
    assert _row(db, old)[0] == 1 and repo.find_successor_source_id(old) == new
    assert _event(db)[0] == "done"


def test_unavailable_mount_defers_not_consumed(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    # old row present in the index, but the mount is gone at drain time
    old = source_id_for("external_file", source_root_key="work", rel_path="old.txt")
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO source_intelligence_sources(source_id,source_kind,source_root_key,"
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
    # 1) reindex returns None -> move committed, event retryable, dest pending, old superseded
    monkeypatch.setattr(si, "index_source_file", lambda *a, **k: None)
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "queued" and code == "dest_reindex_pending"
    assert _row(db, old)[0] == 1 and _row(db, new)[2] == old       # move already committed
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT extraction_status FROM source_intelligence_metadata WHERE source_id=?",
                         (new,)).fetchone()[0] == "pending"
    # 2) reindex recovers (real) on retry -> move_already_applied -> done
    monkeypatch.undo()
    _patch_trust(monkeypatch, safe=True)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_intelligence_events SET next_attempt_at=NULL")
        c.commit()
    drain_queue(repo, config)
    assert _event(db)[0] == "done"
    assert _row(db, new)[2] == old  # lineage not duplicated/altered


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
    # trust-critical invariants still hold: move committed, dest pending (never advertised complete)
    assert _row(db, old)[0] == 1 and _row(db, new)[2] == old


# ---------------- pre/post-transaction identity drift ----------------

def test_pre_transaction_drift_keeps_old_current(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    old = _index_file(root, "old.txt", "x", repo, config)
    (root / "new.txt").write_text("x moved")
    _enqueue_move(repo, "old.txt", "new.txt")
    monkeypatch.setattr(si, "_same_identity", lambda a, b: False)  # drift detected pre-mutation
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
    # pass the pre-move identity check, fail the post-move one (drift AFTER the transaction).
    calls = {"n": 0}

    def _ident(a, b):
        calls["n"] += 1
        return calls["n"] == 1

    monkeypatch.setattr(si, "_same_identity", _ident)
    drain_queue(repo, config)
    st, code, _ = _event(db)
    assert st == "queued" and code == "dest_changed_during_move"
    # old is already SUPERSEDED (not restored); dest pending, never advertised complete
    assert _row(db, old)[0] == 1 and _row(db, new)[2] == old
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT extraction_status FROM source_intelligence_metadata WHERE source_id=?",
                         (new,)).fetchone()[0] == "pending"


# ---------------- queue safety ----------------

def test_defer_conflict_when_event_not_processing(tmp_path) -> None:
    db, root, config, repo = _env(tmp_path)
    eid = repo.enqueue_event(event_type="moved", rel_path="a.txt", dest_rel_path="b.txt",
                             source_root_key="work")
    # event is 'queued', not 'processing' -> defer must fail closed
    assert repo.defer_event(eid, error_code="x", attempts=1) == "conflict"


def test_moved_invalid_payload_is_terminal(tmp_path, monkeypatch) -> None:
    db, root, config, repo = _env(tmp_path)
    _patch_trust(monkeypatch, safe=True)
    repo.enqueue_event(event_type="moved", rel_path="a.txt", dest_rel_path="a.txt",
                       source_root_key="work")  # old == new
    drain_queue(repo, config)
    assert _event(db)[:2] == ("skipped", "moved_invalid")
