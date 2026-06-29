"""A1.10 Defects 1 & 2 — SourceWatcher.start()/status() honor a passed-in (fresh) config."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_watch import SourceWatcher
from hb_assistant.store.migrator import SQLiteMigrator


def _cfg(vault: Path, *, watch: bool) -> ObsidianMcpConfig:
    return ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "external_source_watch_enabled": watch, "watch_poll_interval_seconds": 1,
    })


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "w.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_start_honors_freshly_passed_config(tmp_path: Path) -> None:
    """A watcher built with watch=false starts when start(config=watch-true) is passed (no restart)."""
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    db = _db(tmp_path)
    # Built with watch DISABLED (simulating boot before the operator PATCHed it on).
    w = SourceWatcher(db, _cfg(vault, watch=False))
    try:
        w.start(config=_cfg(vault, watch=True))  # HTTP layer passes the fresh on-disk config
        st = w.status(config=_cfg(vault, watch=True))
        assert st["watch_enabled"] is True
        assert st["running"] is True
        assert st["mode"] in ("watchdog", "polling")
    finally:
        w.stop()


def test_status_consistent_after_stop_and_config_false(tmp_path: Path) -> None:
    """Stop + a fresh watch=false config must report watch_enabled=false (no stale nested true)."""
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    db = _db(tmp_path)
    # Built with watch ENABLED; running.
    w = SourceWatcher(db, _cfg(vault, watch=True))
    w.start()
    assert w.status()["running"] is True
    w.stop()
    # Operator PATCHed watch off; the HTTP layer passes the fresh (false) config to status().
    st = w.status(config=_cfg(vault, watch=False))
    assert st["running"] is False
    assert st["mode"] == "stopped"
    assert st["watch_enabled"] is False  # not the manager's stale true snapshot


def test_status_running_and_config_true_reports_true(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    db = _db(tmp_path)
    w = SourceWatcher(db, _cfg(vault, watch=True))
    try:
        w.start()
        st = w.status(config=_cfg(vault, watch=True))
        assert st["running"] is True and st["watch_enabled"] is True
    finally:
        w.stop()


def test_status_default_config_unchanged_for_unit_callers(tmp_path: Path) -> None:
    """Calling status() with no config uses the injected snapshot (existing unit behavior)."""
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    db = _db(tmp_path)
    w = SourceWatcher(db, _cfg(vault, watch=False))
    w.start()  # no config arg → injected (disabled) snapshot
    st = w.status()
    assert st["running"] is False and st["mode"] == "stopped" and st["watch_enabled"] is False
    w.stop()
