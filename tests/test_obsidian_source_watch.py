"""SourceWatcher: gating, polling fallback, durable queue, real-time indexing."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_watch import SourceWatcher
from hb_assistant.store.migrator import SQLiteMigrator


def _setup(tmp_path: Path, *, watch: bool) -> tuple[str, ObsidianMcpConfig, Path]:
    db = str(tmp_path / "w.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    (root / "22-101-00").mkdir(parents=True, exist_ok=True)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault),
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
        "external_source_watch_enabled": watch, "watch_poll_interval_seconds": 1,
    })
    return db, config, root


def test_disabled_does_not_start(tmp_path: Path) -> None:
    db, config, _root = _setup(tmp_path, watch=False)
    w = SourceWatcher(db, config)
    w.start()
    st = w.status()
    assert st["running"] is False and st["mode"] == "stopped"
    w.stop()


def test_status_shape(tmp_path: Path) -> None:
    db, config, _root = _setup(tmp_path, watch=False)
    st = SourceWatcher(db, config).status()
    for key in ("running", "mode", "watch_enabled", "queued_count", "last_event_at",
                "last_error_code", "roots"):
        assert key in st
    assert st["roots"][0]["key"] == "proj"


def test_poll_once_indexes(tmp_path: Path) -> None:
    db, config, root = _setup(tmp_path, watch=False)
    (root / "22-101-00" / "RFI conduit.md").write_text("Underground conduit", encoding="utf-8")
    w = SourceWatcher(db, config)
    w._poll_once()
    repo = SourceIndexRepository(db)
    assert repo.lookup_by_path("external_file", "22-101-00/RFI conduit.md") is not None
    assert repo.search_sources("conduit")


def test_polling_fallback_when_watchdog_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, config, root = _setup(tmp_path, watch=True)
    (root / "doc.md").write_text("tunnel note", encoding="utf-8")

    def _boom(self: SourceWatcher) -> None:
        raise ImportError("watchdog not installed")

    monkeypatch.setattr(SourceWatcher, "_start_watchdog", _boom)
    w = SourceWatcher(db, config)
    w.start()
    try:
        assert w.status()["mode"] == "polling"
        repo = SourceIndexRepository(db)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if repo.lookup_by_path("external_file", "doc.md") is not None:
                break
            time.sleep(0.1)
        assert repo.lookup_by_path("external_file", "doc.md") is not None
    finally:
        w.stop()
    assert w.status()["running"] is False


def test_durable_queue_survives_new_watcher(tmp_path: Path) -> None:
    db, config, _root = _setup(tmp_path, watch=False)
    SourceIndexRepository(db).enqueue_event(event_type="modified", rel_path="x/y.md", source_root_key="proj")
    # A fresh watcher/repo over the same DB still sees the queued work.
    assert SourceIndexRepository(db).index_status()["queued_count"] == 1


def test_watchdog_indexes_on_create(tmp_path: Path) -> None:
    pytest.importorskip("watchdog")
    db, config, root = _setup(tmp_path, watch=True)
    w = SourceWatcher(db, config)
    w.start()
    try:
        assert w.status()["mode"] == "watchdog"
        (root / "22-101-00" / "Late RFI conduit.md").write_text("conduit added live", encoding="utf-8")
        repo = SourceIndexRepository(db)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if repo.lookup_by_path("external_file", "22-101-00/Late RFI conduit.md") is not None:
                break
            time.sleep(0.2)
        assert repo.lookup_by_path("external_file", "22-101-00/Late RFI conduit.md") is not None
    finally:
        w.stop()
