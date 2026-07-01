"""External-source watcher — runs OFF the asyncio event loop in a daemon thread.

Prefers watchdog real-time filesystem events; falls back to a periodic polling scan when
watchdog is not installed. Events are written to the durable ``source_intelligence_events``
queue (coalesced per path) and drained by the worker, so changes survive a backend restart.
Indexing never runs on the request loop and never blocks startup/shutdown.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ObsidianMcpConfig, load_config
from .source_index_repository import SourceIndexRepository
from .source_indexer import (
    _VAULT_ROOT_KEY,
    drain_queue,
    is_email_archive_path,
    is_source_notes_path,
    scan_source_root,
    scan_vault_notes,
    should_ignore,
)

_logger = logging.getLogger("hb_assistant.obsidian_mcp.source_watch")

# Lease staleness TTL — mirrors the requeue_stuck TTL so a crashed owner's in-flight events and its
# lease both become reclaimable on the same horizon.
WATCHER_LEASE_TTL_SECONDS = 900


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enabled_roots(config: ObsidianMcpConfig) -> list[Any]:
    return [r for r in getattr(config, "external_sources", []) or [] if r.enabled]


def _roots_hash(config: ObsidianMcpConfig, db_path: str) -> str:
    """Stable short hash of the (db, vault, enabled-roots) context this watcher would own."""
    payload = json.dumps(
        {
            "db": str(db_path),
            "vault": getattr(config, "vault_root", None),
            "roots": sorted((r.source_root_key, r.path) for r in _enabled_roots(config)),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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
        self._last_test_event_at: str | None = None
        # Single-owner lease: an opaque per-watcher nonce identifies this instance's ownership.
        self._owner_token = uuid.uuid4().hex
        self._is_owner = False
        self._degraded = False

    # ----- lifecycle -------------------------------------------------------------------------
    def start(self, *, config: ObsidianMcpConfig | None = None) -> None:
        # Honor a freshly-loaded config (HTTP layer passes the current on-disk config so a just-
        # PATCHed external_source_watch_enabled takes effect WITHOUT a process restart). Default
        # None keeps the injected snapshot (so direct unit tests are unchanged).
        if config is not None:
            self._config = config
        if not getattr(self._config, "external_source_watch_enabled", False):
            self._mode = "stopped"
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        # Single-owner guard: only one backend may run the drain loop against this DB/root context.
        # FAIL CLOSED: if ownership cannot be proven — a competing live owner OR a lease-check error
        # — this instance serves the API but stays degraded (no drain thread, no observer). Better a
        # quiet/degraded watcher than two uncoordinated drains racing the same DB/source roots.
        owner_info = {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "db_path": str(self._db_path),
            "roots_hash": _roots_hash(self._config, str(self._db_path)),
        }
        try:
            lease = self._repo.acquire_watcher_lease(
                owner_token=self._owner_token, owner_info=owner_info,
                ttl_seconds=WATCHER_LEASE_TTL_SECONDS,
            )
        except Exception:  # lease-check error: cannot prove ownership → degrade, do NOT drain
            self._is_owner = False
            self._degraded = True
            self._mode = "degraded"
            self._last_error_code = "watcher_lease_error"  # safe, sanitized (no exception detail)
            _logger.warning("source_watch.degraded_lease_error", extra={"obsidian_mcp": {
                "error_code": "watcher_lease_error"}})
            return
        if not lease.get("acquired", True):
            self._is_owner = False
            self._degraded = True
            self._mode = "degraded"
            self._last_error_code = "watcher_not_owner"
            _logger.warning("source_watch.degraded_not_owner", extra={"obsidian_mcp": {
                "owner_pid": (lease.get("owner") or {}).get("pid")}})
            return
        self._is_owner = True
        self._degraded = False
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
        # Release the lease only if we actually own it (a degraded non-owner must never clear the
        # live owner's lease).
        if self._is_owner:
            with suppress(Exception):
                self._repo.release_watcher_lease(owner_token=self._owner_token)
        self._is_owner = False
        self._degraded = False

    def restart(self) -> dict[str, Any]:
        """Stop, reload config from disk (so config edits take effect), and start again."""
        self.stop()
        fresh = load_config()
        self.start(config=fresh)
        return self.status(config=fresh)

    def recover_stuck(self, ttl_seconds: int = 900) -> dict[str, Any]:
        """Re-queue events stuck in 'processing' past the TTL (operator manual recovery)."""
        requeued = self._repo.requeue_stuck(ttl_seconds)
        return {"requeued": int(requeued), "ttl_seconds": int(ttl_seconds)}

    def test_event(self) -> dict[str, Any]:
        """Enqueue a bounded rebuild event and drain it synchronously to prove the pipe works.

        Targets the first enabled external root, else the vault root. Never writes to external
        source files (a scan only reads them and writes index rows). Safe alongside a running
        worker — claim_queued atomically claims, so no double-processing.
        """
        roots = _enabled_roots(self._config)
        target = roots[0].source_root_key if roots else _VAULT_ROOT_KEY
        self._repo.enqueue_event(event_type="rebuild", source_root_key=target)
        self._last_test_event_at = _now()
        processed = drain_queue(self._repo, self._config)
        return {
            "enqueued": True,
            "source_root_key": target,
            "processed": int(processed),
            "queue": self._repo.queue_health(),
        }

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
                # Vault watcher: ignore our own generated source cards (Source Notes/...) and
                # full-email archive notes (Email Archive/...) so our own writes don't re-enter
                # source processing (and archive bodies never reach the FTS). Vault root only.
                if self._root_key == _VAULT_ROOT_KEY and (
                        is_source_notes_path(rel, config) or is_email_archive_path(rel)):
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
                with suppress(Exception):
                    self._repo.refresh_watcher_heartbeat(owner_token=self._owner_token)
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
    def status(self, *, config: ObsidianMcpConfig | None = None) -> dict[str, Any]:
        # ``running``/``mode`` reflect the real thread state; ``watch_enabled``/``roots`` are derived
        # from ``config`` (the HTTP layer passes the current on-disk config) so the reported state is
        # internally consistent with the top-level config-derived ``watch_enabled`` and never stale.
        cfg = config if config is not None else self._config
        running = self._thread is not None and self._thread.is_alive()
        health: dict[str, Any] = {}
        try:
            health = self._repo.queue_health()
        except Exception:
            health = {}
        owner: dict[str, Any] | None = None
        with suppress(Exception):
            owner = self._repo.get_watcher_owner(ttl_seconds=WATCHER_LEASE_TTL_SECONDS)
        if owner is not None:
            # Redact the internal ownership nonce; keep the operator-useful diagnostics
            # (pid/cwd/db_path/roots_hash/started_at/heartbeat). No bearer token is ever in here.
            owner = {k: v for k, v in owner.items() if k != "owner_token"}
        return {
            "running": running,
            "mode": self._mode,
            "watch_enabled": bool(getattr(cfg, "external_source_watch_enabled", False)),
            "degraded": bool(self._degraded),
            "is_owner": bool(self._is_owner),
            "owner": owner,
            "queued_count": health.get("queued_count"),
            "queue_health": health,
            "last_event_at": self._last_event_at,
            "last_test_event_at": self._last_test_event_at,
            "last_error_code": self._last_error_code,
            "roots": [{"key": r.source_root_key, "path": r.path, "enabled": r.enabled,
                       "sensitive": bool(getattr(r, "sensitive", False))}
                      for r in getattr(cfg, "external_sources", []) or []],
        }
