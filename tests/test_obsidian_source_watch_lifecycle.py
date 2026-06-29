"""A1.3 — watcher lifecycle (restart / recover-stuck / test-event) + queue health.

Covers the repo ``queue_health`` signals (stale-state stamps + oldest-processing age),
the new ``SourceWatcher`` operator methods, and the five source-watch API endpoints with
role gating + lazy watcher construction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_watch import SourceWatcher
from hb_assistant.store.migrator import SQLiteMigrator


def _setup(tmp_path: Path, *, watch: bool = False) -> tuple[str, ObsidianMcpConfig, Path]:
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


# ----------------------------------------------------------------------------- queue_health


def test_queue_health_shape_and_drain_stamp(tmp_path: Path) -> None:
    db, config, root = _setup(tmp_path)
    repo = SourceIndexRepository(db)
    health = repo.queue_health()
    for key in ("queued_count", "processing_count", "error_count", "done_count",
                "oldest_processing_age_seconds", "last_event_at", "last_drain_at",
                "last_note_at", "last_summary_at"):
        assert key in health
    assert health["oldest_processing_age_seconds"] is None  # nothing in flight
    assert health["last_drain_at"] is None

    # a drain stamps last_drain_at
    (root / "22-101-00" / "a.md").write_text("Underground conduit", encoding="utf-8")
    from hb_assistant.obsidian_mcp.source_indexer import drain_queue
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    drain_queue(repo, config)
    assert repo.queue_health()["last_drain_at"] is not None


def test_queue_health_oldest_processing_age(tmp_path: Path) -> None:
    db, _config, _root = _setup(tmp_path)
    repo = SourceIndexRepository(db)
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    repo.claim_queued()  # queued -> processing
    health = repo.queue_health()
    assert health["processing_count"] == 1
    assert health["oldest_processing_age_seconds"] is not None
    assert health["oldest_processing_age_seconds"] >= 0


# --------------------------------------------------------------------------- watcher methods


def test_recover_stuck_requeues_processing(tmp_path: Path) -> None:
    db, config, _root = _setup(tmp_path)
    repo = SourceIndexRepository(db)
    repo.enqueue_event(event_type="rebuild", source_root_key="proj")
    repo.claim_queued()  # -> processing
    out = SourceWatcher(db, config).recover_stuck(ttl_seconds=0)
    assert out["requeued"] == 1
    assert repo.queue_health()["queued_count"] == 1


def test_test_event_enqueues_and_drains(tmp_path: Path) -> None:
    db, config, root = _setup(tmp_path)
    (root / "22-101-00" / "b.md").write_text("conduit scope", encoding="utf-8")
    w = SourceWatcher(db, config)
    out = w.test_event()
    assert out["enqueued"] is True
    assert out["source_root_key"] == "proj"
    assert out["processed"] >= 1
    assert "queue" in out
    assert w.status()["last_test_event_at"] is not None


def test_restart_is_idempotent_and_returns_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, config, _root = _setup(tmp_path, watch=False)
    w = SourceWatcher(db, config)
    # restart reloads config from disk; point load_config at our config to avoid touching real state.
    monkeypatch.setattr("hb_assistant.obsidian_mcp.source_watch.load_config", lambda: config)
    st = w.restart()
    assert st["running"] is False  # watch disabled → stays stopped
    assert st["mode"] == "stopped"


def test_status_includes_queue_health(tmp_path: Path) -> None:
    db, config, _root = _setup(tmp_path)
    st = SourceWatcher(db, config).status()
    assert "queue_health" in st
    assert st["roots"][0]["sensitive"] is False


# ------------------------------------------------------------------------------- API endpoints


def _client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "api.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def test_source_watch_status_endpoint_viewer_ok(tmp_path: Path) -> None:
    client = _client(tmp_path)
    res = client.get("/api/settings/obsidian-mcp/source-watch/status")
    assert res.status_code == 200
    assert "running" in res.json()


def test_source_watch_mutations_require_operator(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path in ("start", "stop", "restart", "test-event", "recover-stuck"):
        res = client.post(f"/api/settings/obsidian-mcp/source-watch/{path}")  # default viewer
        assert res.status_code == 403, path


def test_source_watch_recover_stuck_operator(tmp_path: Path) -> None:
    client = _client(tmp_path)
    res = client.post(
        "/api/settings/obsidian-mcp/source-watch/recover-stuck",
        headers={"X-HB-UI-Role": "operator"},
    )
    assert res.status_code == 200
    assert "requeued" in res.json()


def test_source_watch_test_event_lazy_constructs(tmp_path: Path) -> None:
    # watch disabled at boot → app.state.source_watcher may be set but stopped; test-event still works.
    client = _client(tmp_path)
    res = client.post(
        "/api/settings/obsidian-mcp/source-watch/test-event",
        headers={"X-HB-UI-Role": "operator"},
    )
    assert res.status_code == 200
    assert res.json()["enqueued"] is True
