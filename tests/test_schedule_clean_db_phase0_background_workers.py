"""Background worker disable gate tests."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.store.migrator import SQLiteMigrator


def _db(tmp_path: Path) -> str:
    db = tmp_path / "bg.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _consume_create_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[None] | None:
    """Close coroutines passed to mocked create_task to avoid RuntimeWarning."""
    coro.close()
    return None


def test_workers_enabled_when_env_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", raising=False)
    with (
        patch(
            "hb_assistant.construction.analytics.api.asyncio.create_task",
            side_effect=_consume_create_task,
        ) as create_task,
        patch("hb_assistant.obsidian_mcp.source_index_repository.SourceIndexRepository") as repo_cls,
        patch("hb_assistant.obsidian_mcp.source_watch.SourceWatcher") as watcher_cls,
    ):
        repo_cls.return_value.register_source_roots = MagicMock()
        watcher_cls.return_value.start = MagicMock()
        app = create_app(db_path=_db(tmp_path))
        with TestClient(app) as client:
            body = client.get("/health", headers={"X-HB-UI-Role": "operator"}).json()
        assert body["background_worker_mode"] == "enabled"
        assert body["background_workers_disabled_by_env"] is False
        assert create_task.called


def test_workers_disabled_when_env_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    with (
        patch(
            "hb_assistant.construction.analytics.api.asyncio.create_task",
            side_effect=_consume_create_task,
        ) as create_task,
        patch("hb_assistant.obsidian_mcp.source_index_repository.SourceIndexRepository") as repo_cls,
        patch("hb_assistant.obsidian_mcp.source_watch.SourceWatcher") as watcher_cls,
    ):
        app = create_app(db_path=_db(tmp_path))
        with TestClient(app) as client:
            body = client.get("/health", headers={"X-HB-UI-Role": "operator"}).json()
        assert body["background_worker_mode"] == "disabled"
        assert body["background_workers_disabled_by_env"] is True
        assert body["background_workers"]["quality_poll_started"] is False
        create_task.assert_not_called()
        repo_cls.return_value.register_source_roots.assert_not_called()
        watcher_cls.return_value.start.assert_not_called()


def test_workers_enabled_for_unexpected_env_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "yes")
    with patch(
        "hb_assistant.construction.analytics.api.asyncio.create_task",
        side_effect=_consume_create_task,
    ) as create_task:
        app = create_app(db_path=_db(tmp_path))
        with TestClient(app) as client:
            body = client.get("/health", headers={"X-HB-UI-Role": "operator"}).json()
        assert body["background_worker_mode"] == "enabled"
        assert body["background_workers_disabled_by_env"] is False
        assert create_task.called
