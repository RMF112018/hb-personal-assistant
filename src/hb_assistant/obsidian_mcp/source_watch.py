"""External-source watcher — runs OFF the asyncio event loop in a daemon thread.

Prefers watchdog real-time filesystem events; falls back to a periodic polling scan when
watchdog is not installed. Events are written to the durable ``source_intelligence_events``
queue (coalesced per path) and drained by the worker, so changes survive a backend restart.
Indexing never runs on the request loop and never blocks startup/shutdown.
"""

from __future__ import annotations

import logging
import threading
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ObsidianMcpConfig
from .source_index_repository import SourceIndexRepository
from .source_indexer import (
    _VAULT_ROOT_KEY,
    drain_queue,
    scan_source_root,
    scan_vault_notes,
    should_ignore,
)

_logger = logging.getLogger("hb_assistant.obsidian_mcp.source_watch")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enabled_roots(config: ObsidianMcpConfig) -> list[Any]:
    return [r for r in getattr(config, "external_sources", []) or [] if r.enabled]


class SourceWatcher:
    """Owns a daemon worker thread (watchdog observer or polling). Idempotent start/stop."""

    def __init__(self, db_path: str, config: ObsidianMcpConfig) -> None:
        self._db_path = db_path
        self._config = config
        self._repo = SourceIndexRepository(db_path)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._observer: Any = None
        self._mode = "stopped"
        self._last_event_at: str | None = None
        self._last_error_code: str | None = None

    # ----- lifecycle -------------------------------------------------------------------------
    def start(self) -> None:
        if not getattr(self._config, "external_source_watch_enabled", False):
            self._mode = "stopped"
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        with suppress(Exception):
            self._repo.requeue_stuck()  # recover events stuck in 'processing' from a prior run
        try:
            self._start_watchdog()
            self._mode = "watchdog"
        except Exception as exc:  # watchdog missing or failed → polling
            self._last_error_code = type(exc).__name__
            self._mode = "polling"
        self._thread = threading.Thread(target=self._run, name="source-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            with suppress(Exception):
                self._observer.stop()
                self._observer.join(timeout=2)
            self._observer = None
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        self._mode = "stopped"

    # ----- watchdog path ---------------------------------------------------------------------
    def _start_watchdog(self) -> None:
        from watchdog.events import FileSystemEventHandler  # noqa: PLC0415
        from watchdog.observers import Observer  # noqa: PLC0415

        repo, config = self._repo, self._config
        watcher = self

        class _Handler(FileSystemEventHandler):  # type: ignore[misc]
            def __init__(self, root_key: str, root_path: Path) -> None:
                self._root_key = root_key
                self._root_path = root_path

            def _enqueue(self, src_path: str, event_type: str) -> None:
                try:
                    rel = str(Path(src_path).relative_to(self._root_path))
                except ValueError:
                    return
                if should_ignore(rel, Path(src_path).name):
                    return
                repo.enqueue_event(event_type=event_type, rel_path=rel, source_root_key=self._root_key)
                watcher._last_event_at = _now()

            def on_created(self, event: Any) -> None:
                if not event.is_directory:
                    self._enqueue(event.src_path, "created")

            def on_modified(self, event: Any) -> None:
                if not event.is_directory:
                    self._enqueue(event.src_path, "modified")

            def on_deleted(self, event: Any) -> None:
                if not event.is_directory:
                    self._enqueue(event.src_path, "deleted")

            def on_moved(self, event: Any) -> None:
                if not event.is_directory:
                    self._enqueue(event.src_path, "deleted")
                    self._enqueue(getattr(event, "dest_path", event.src_path), "created")

        observer = Observer()
        for root in _enabled_roots(config):
            root_path = Path(root.path)
            if root_path.is_dir():
                observer.schedule(_Handler(root.source_root_key, root_path), str(root_path), recursive=True)
        vault_root = Path(config.vault_root)
        if vault_root.is_dir():
            observer.schedule(_Handler(_VAULT_ROOT_KEY, vault_root), str(vault_root), recursive=True)
        observer.start()
        self._observer = observer

    # ----- worker loop -----------------------------------------------------------------------
    def _run(self) -> None:
        poll_interval = float(getattr(self._config, "watch_poll_interval_seconds", 30))
        while not self._stop.is_set():
            try:
                if self._mode == "polling":
                    self._poll_once()
                drain_queue(self._repo, self._config)
            except Exception as exc:  # never let the worker die
                self._last_error_code = type(exc).__name__
                _logger.warning("source_watch.worker_error", extra={"obsidian_mcp": {
                    "error_code": type(exc).__name__}})
            self._stop.wait(poll_interval if self._mode == "polling" else 2.0)

    def _poll_once(self) -> None:
        for root in _enabled_roots(self._config):
            scan_source_root(root, self._repo, self._config)
            self._last_event_at = _now()
        scan_vault_notes(self._repo, self._config)

    # ----- status ----------------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        running = self._thread is not None and self._thread.is_alive()
        try:
            queued = self._repo.index_status()["queued_count"]
        except Exception:
            queued = None
        return {
            "running": running,
            "mode": self._mode,
            "watch_enabled": bool(getattr(self._config, "external_source_watch_enabled", False)),
            "queued_count": queued,
            "last_event_at": self._last_event_at,
            "last_error_code": self._last_error_code,
            "roots": [{"key": r.source_root_key, "path": r.path, "enabled": r.enabled}
                      for r in getattr(self._config, "external_sources", []) or []],
        }
