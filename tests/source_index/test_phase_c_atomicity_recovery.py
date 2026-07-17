"""PC-WI-03 Stage-2 — atomicity, interruption, recovery, and locking (PC-AC-036..039).

Proves, against validated legacy source-index fixtures under a caller rehearsal root, that:

- PC-AC-036 — migration lock/busy behavior is **bounded**: a competing write lock makes ``apply()``
  fail with "database is locked" within its busy-timeout rather than hanging indefinitely.
- PC-AC-037 — an interruption during the migrator's single atomic ``apply()`` transaction leaves the
  origin database **logically unchanged** after SQLite recovery (or the test fails closed).
- PC-AC-038 — a recoverable interruption **reruns to head** without duplicated migrations or
  corruption (ledger holds every version 1..127 exactly once).
- PC-AC-039 — an **unrecoverable integrity failure blocks completion**: the fail-closed read-only
  engine refuses to report a corrupt database as valid.

The kill-mid-``apply()`` proof (PCR-005) uses a fresh-interpreter child harness with a deterministic
``sqlite3`` trace-callback barrier and an IPC file signal — never a timing sleep. A **harness
self-test** rejects a vacuous proof: the barrier must fire and the child must still be alive (holding
the transaction open) at kill time, else the test fails rather than passes.
"""

from __future__ import annotations

import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

import tests.support.source_index_atomicity_child as atomicity_child
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_migration_assurance import (
    collect_inventory,
    source_index_logical_hash,
)
from tests.support.source_index_migration_fixture import HEAD_VERSION, build_fixture

_CHILD = Path(atomicity_child.__file__)
_BARRIER_VERSION = 124  # strictly above the origin-121 fixture, so it runs inside the open transaction
_FAILSAFE_S = 60.0  # upper bound only; the barrier is the IPC file, not this timeout
_SUBPROCESS_PYTHONPATH = "src:subrepos/construction-financial-review/src"


def _rehearsal(tmp_path: Path) -> Path:
    root = tmp_path / "rehearsal"
    root.mkdir()
    return root


def _max_version(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
    finally:
        conn.close()


def _ledger_versions(db: Path) -> list[int]:
    conn = sqlite3.connect(str(db))
    try:
        return [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    finally:
        conn.close()


def _recover(db: Path) -> None:
    """Open a fresh connection (forcing WAL/journal recovery) and truncate the WAL so the fail-closed
    read-only inventory engine — which rejects a non-empty ``-wal`` — can inspect the recovered DB."""
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("PRAGMA quick_check")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _kill_mid_apply(db: Path, signal_path: Path) -> tuple[bool, bool]:
    """Spawn a fresh-interpreter child that begins ``apply()`` and blocks at the barrier, then SIGKILL
    it mid-transaction. Returns ``(barrier_fired, alive_at_kill)`` for the harness self-test."""
    env = dict(os.environ)
    env["PYTHONPATH"] = _SUBPROCESS_PYTHONPATH
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_CHILD),
            "--db",
            str(db),
            "--signal",
            str(signal_path),
            "--barrier-version",
            str(_BARRIER_VERSION),
        ],
        env=env,
    )
    fired = False
    deadline = time.monotonic() + _FAILSAFE_S
    while time.monotonic() < deadline:
        if signal_path.exists():
            fired = True
            break
        if proc.poll() is not None:  # child exited before the barrier — proof would be vacuous
            break
        time.sleep(0.02)
    alive = proc.poll() is None
    if alive:
        os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    return fired, alive


def _assert_genuine_interruption(fired: bool, alive: bool) -> None:
    # Harness self-test: a vacuous proof must fail closed, never pass silently.
    assert fired, "atomicity barrier never fired — kill-mid-apply proof is vacuous (INSUFFICIENT EVIDENCE)"
    assert alive, "child completed before interruption — mid-transaction atomicity was not exercised"


def test_interruption_mid_apply_leaves_origin_logically_unchanged(tmp_path: Path) -> None:  # PC-AC-037
    root = _rehearsal(tmp_path)
    fx = build_fixture(root, 121, row_count=6, filename="src.sqlite")
    db = fx.db_path
    origin_version = _max_version(db)
    origin_hash = source_index_logical_hash(db)
    assert origin_version == 121

    fired, alive = _kill_mid_apply(db, root / "barrier.signal")
    _assert_genuine_interruption(fired, alive)

    _recover(db)
    inv = collect_inventory(db)
    assert inv.integrity.quick_check == "ok" and inv.integrity.integrity_check == "ok"
    assert inv.integrity.foreign_key_violations == 0
    assert _max_version(db) == origin_version  # atomic rollback to origin head
    assert source_index_logical_hash(db) == origin_hash  # logical inventory unchanged


def test_recoverable_interruption_reruns_to_head_without_duplicates(tmp_path: Path) -> None:  # PC-AC-038
    root = _rehearsal(tmp_path)
    fx = build_fixture(root, 121, row_count=6, filename="src.sqlite")
    db = fx.db_path

    fired, alive = _kill_mid_apply(db, root / "barrier.signal")
    _assert_genuine_interruption(fired, alive)

    _recover(db)
    assert _max_version(db) == 121  # rolled back before the rerun

    version = SQLiteMigrator(db_path=str(db)).apply()  # rerun migration to head (owned connection)
    assert version == HEAD_VERSION

    _recover(db)
    inv = collect_inventory(db)
    assert inv.integrity.integrity_check == "ok" and inv.integrity.quick_check == "ok"
    assert inv.integrity.foreign_key_violations == 0
    versions = _ledger_versions(db)
    assert versions == list(range(1, HEAD_VERSION + 1))  # every version once, no gaps
    assert len(versions) == len(set(versions))  # no duplicates


def test_migration_lock_busy_behavior_is_bounded(tmp_path: Path) -> None:  # PC-AC-036
    root = _rehearsal(tmp_path)
    fx = build_fixture(root, 124, row_count=6, filename="src.sqlite")
    db = fx.db_path

    holder = sqlite3.connect(str(db))
    holder.execute("BEGIN IMMEDIATE")  # hold the write lock for the whole attempt
    holder.execute("PRAGMA user_version = 42")
    try:
        blocked = sqlite3.connect(str(db), timeout=0.5)
        blocked.execute("PRAGMA busy_timeout = 500")  # bounded 500ms busy handler
        start = time.monotonic()
        with pytest.raises(sqlite3.OperationalError) as exc_info:
            SQLiteMigrator(db_path=str(db)).apply(conn=blocked)
        elapsed = time.monotonic() - start
        blocked.close()
        assert "locked" in str(exc_info.value).lower()
        assert elapsed < 10.0  # bounded — did not hang indefinitely on the held lock
    finally:
        holder.rollback()
        holder.close()


def test_unrecoverable_integrity_failure_blocks_completion(tmp_path: Path) -> None:  # PC-AC-039
    root = _rehearsal(tmp_path)
    fx = build_fixture(root, 124, row_count=6, filename="src.sqlite")
    db = fx.db_path
    assert collect_inventory(db).integrity.integrity_check == "ok"  # baseline is sane

    # Deterministic, unrecoverable corruption: clobber a b-tree region past the header/page-1.
    data = bytearray(db.read_bytes())
    assert len(data) > 8192
    for offset in range(4096, 4096 + 1024):
        data[offset] ^= 0xFF
    db.write_bytes(bytes(data))

    # The fail-closed read-only completion gate must block: raise, or report integrity != ok.
    blocked = False
    try:
        inv = collect_inventory(db)
        if inv.integrity.integrity_check != "ok" or inv.integrity.quick_check != "ok":
            blocked = True
    except sqlite3.DatabaseError:
        blocked = True
    assert blocked, "a corrupt database must block completion (fail-closed), never report success"
