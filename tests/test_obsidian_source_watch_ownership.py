"""Single-owner watcher lease: only one backend drains; stale/dead owners are reclaimable."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_watch import SourceWatcher
from hb_assistant.store.migrator import SQLiteMigrator

_OLD = "2000-01-01T00:00:00+00:00"  # a long-dead owner's heartbeat


def _repo(tmp_path: Path) -> tuple[SourceIndexRepository, str]:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return SourceIndexRepository(db), db


def _backdate_heartbeat(db: str) -> None:
    with sqlite3.connect(db) as c:
        c.execute(
            "UPDATE source_intelligence_state SET state_value=? WHERE state_key='watcher_heartbeat_at'",
            (_OLD,),
        )
        c.commit()


# ----- repository-level lease (deterministic, no threads) ------------------------------------
def test_acquire_first_owner(tmp_path: Path) -> None:
    repo, _db = _repo(tmp_path)
    res = repo.acquire_watcher_lease(owner_token="A", owner_info={"pid": 111, "cwd": "/x"})
    assert res["acquired"] is True
    assert res["took_over"] is False
    owner = repo.get_watcher_owner()
    assert owner is not None
    assert owner["pid"] == 111
    assert owner["owner_token"] == "A"
    assert owner["stale"] is False


def test_second_owner_refused_when_fresh(tmp_path: Path) -> None:
    repo, _db = _repo(tmp_path)
    repo.acquire_watcher_lease(owner_token="A", owner_info={"pid": 1})
    res = repo.acquire_watcher_lease(owner_token="B", owner_info={"pid": 2})
    assert res["acquired"] is False
    assert res["owner"]["owner_token"] == "A"
    assert repo.get_watcher_owner()["owner_token"] == "A"  # A still owns


def test_reentry_same_owner_preserves_started_at(tmp_path: Path) -> None:
    repo, _db = _repo(tmp_path)
    r1 = repo.acquire_watcher_lease(owner_token="A", owner_info={"pid": 1})
    r2 = repo.acquire_watcher_lease(owner_token="A", owner_info={"pid": 1})
    assert r1["acquired"] and r2["acquired"]
    assert r2["owner"]["started_at"] == r1["owner"]["started_at"]


def test_stale_owner_reclaimed(tmp_path: Path) -> None:
    repo, db = _repo(tmp_path)
    repo.acquire_watcher_lease(owner_token="A", owner_info={"pid": 1})
    _backdate_heartbeat(db)  # simulate a crashed owner
    res = repo.acquire_watcher_lease(owner_token="B", owner_info={"pid": 2})
    assert res["acquired"] is True
    assert res["took_over"] is True
    assert repo.get_watcher_owner()["owner_token"] == "B"


def test_refresh_and_release_require_ownership(tmp_path: Path) -> None:
    repo, _db = _repo(tmp_path)
    repo.acquire_watcher_lease(owner_token="A", owner_info={"pid": 1})
    assert repo.refresh_watcher_heartbeat(owner_token="B") is False
    assert repo.refresh_watcher_heartbeat(owner_token="A") is True
    assert repo.release_watcher_lease(owner_token="B") is False
    assert repo.release_watcher_lease(owner_token="A") is True
    assert repo.get_watcher_owner() is None


def test_get_watcher_owner_marks_stale(tmp_path: Path) -> None:
    repo, db = _repo(tmp_path)
    repo.acquire_watcher_lease(owner_token="A", owner_info={"pid": 1})
    _backdate_heartbeat(db)
    assert repo.get_watcher_owner()["stale"] is True


# ----- watcher-level integration -------------------------------------------------------------
def _watch_setup(tmp_path: Path, *, watch: bool) -> tuple[str, ObsidianMcpConfig]:
    db = str(tmp_path / "w.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
        "external_source_watch_enabled": watch, "watch_poll_interval_seconds": 1,
    })
    return db, config


def _force_polling(self: SourceWatcher) -> None:
    raise ImportError("forced polling for deterministic test")


def test_second_watcher_runs_degraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, config = _watch_setup(tmp_path, watch=True)
    monkeypatch.setattr(SourceWatcher, "_start_watchdog", _force_polling)
    w1 = SourceWatcher(db, config)
    w2 = SourceWatcher(db, config)
    w1.start()
    try:
        w2.start()  # w1 holds a fresh lease → w2 must not become a competing drain owner
        st = w2.status()
        assert st["degraded"] is True
        assert st["is_owner"] is False
        assert st["running"] is False
        assert st["mode"] == "degraded"
        assert st["last_error_code"] == "watcher_not_owner"
        assert w1.status()["is_owner"] is True  # w1 stays the active owner
    finally:
        w1.stop()
        w2.stop()


def test_owner_released_on_stop_lets_next_acquire(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, config = _watch_setup(tmp_path, watch=True)
    monkeypatch.setattr(SourceWatcher, "_start_watchdog", _force_polling)
    w1 = SourceWatcher(db, config)
    w1.start()
    assert w1.status()["is_owner"] is True
    w1.stop()  # releases the lease
    w2 = SourceWatcher(db, config)
    try:
        w2.start()
        assert w2.status()["is_owner"] is True
        assert w2.status()["degraded"] is False
    finally:
        w2.stop()


def test_status_owner_redacts_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, config = _watch_setup(tmp_path, watch=True)
    monkeypatch.setattr(SourceWatcher, "_start_watchdog", _force_polling)
    w = SourceWatcher(db, config)
    w.start()
    try:
        owner = w.status()["owner"]
        assert owner is not None
        assert "owner_token" not in owner            # internal nonce redacted from status
        assert owner["pid"] == os.getpid()
        assert "db_path" in owner and "roots_hash" in owner
    finally:
        w.stop()


def test_lease_check_error_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lease-check DB error must NOT start the drain — degrade with a safe code (fail-closed)."""
    db, config = _watch_setup(tmp_path, watch=True)
    # If the guard wrongly reached the drain loop, this would surface; it must not be hit.
    monkeypatch.setattr(SourceWatcher, "_start_watchdog", _force_polling)
    w = SourceWatcher(db, config)

    def _boom(*_a: object, **_k: object) -> dict[str, object]:
        raise sqlite3.OperationalError("lease table unavailable")

    monkeypatch.setattr(w._repo, "acquire_watcher_lease", _boom)
    w.start()
    try:
        st = w.status()  # API/status surface stays available
        assert st["degraded"] is True
        assert st["is_owner"] is False
        assert st["running"] is False              # no active drain thread started
        assert st["mode"] == "degraded"
        assert st["last_error_code"] == "watcher_lease_error"  # safe, sanitized code
        assert isinstance(st["queue_health"], dict)            # status still serves cleanly
        # No ownership was recorded (the failed acquire wrote nothing).
        assert w._repo.get_watcher_owner() is None
    finally:
        w.stop()
