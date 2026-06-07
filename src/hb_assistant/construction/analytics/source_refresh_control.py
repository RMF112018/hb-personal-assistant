"""Source-refresh control service for the analytics UI shell.

Wraps the in-process ``SourceRefreshOrchestrator`` in three safe, UI-facing modes:

- dry-run: plan only — never writes the SQLite DB.
- local/mock: rebuild local SQLite only — never constructs a live Graph/Procore client.
- live: fail closed unless the running environment is production, server config enables live reads,
  AND the caller passes an explicit confirmation. Even when permitted, the orchestrator independently
  fails closed on missing ``HB_PROCORE_LIVE`` / auth-not-ready.

All three return the orchestrator's metadata-only summary (no raw payloads). The vault/vector stages are
skipped (``skip_vector`` + ``skip_daily_brief_proof``) so the action stays scoped to source data and has
no vault/vector side effects.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any, Iterator

from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.procore.live_gate import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.source_refresh.orchestrator import RefreshOptions, SourceRefreshOrchestrator

_BASE: dict[str, Any] = {"all_": True, "skip_vector": True, "skip_daily_brief_proof": True}


@contextlib.contextmanager
def _maybe_live_env(enable: bool) -> Iterator[None]:
    """Set HB_PROCORE_LIVE=1 only for the duration of a permitted live run, then restore."""
    if not enable:
        yield
        return
    prior = os.environ.get(LIVE_ENV_VAR)
    os.environ[LIVE_ENV_VAR] = LIVE_ENV_ENABLER
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(LIVE_ENV_VAR, None)
        else:
            os.environ[LIVE_ENV_VAR] = prior


class SourceRefreshControlService:
    """In-process driver for the UI-facing source-refresh actions."""

    def __init__(self, *, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._config = load_config()
        self._pp = PathPolicy(self._config)

    def _environment(self) -> str:
        root = self._pp.get_app_support()
        return "dev" if root.name.endswith("(Dev)") else "production"

    def _orchestrator(self) -> SourceRefreshOrchestrator:
        return SourceRefreshOrchestrator(db_path=Path(self._db_path) if self._db_path else None)

    def dry_run(self) -> dict[str, Any]:
        options = RefreshOptions(
            **_BASE,
            apply=False,
            confirm=False,
            mock_data=False,
            allow_procore_live=False,
            allow_graph_live=False,
        )
        summary = self._orchestrator().run(options=options)
        summary["surface"] = "analytics.sources.refresh.dry_run"
        return summary

    def local(self) -> dict[str, Any]:
        options = RefreshOptions(
            **_BASE,
            apply=True,
            confirm=True,
            mock_data=True,
            allow_procore_live=False,
            allow_graph_live=False,
        )
        summary = self._orchestrator().run(options=options)
        summary["surface"] = "analytics.sources.refresh.local"
        return summary

    def live(self, *, confirm: bool) -> dict[str, Any]:
        environment = self._environment()
        scheduler = self._config.automation.scheduler
        config_enabled = bool(scheduler.enable_live_reads)

        if environment != "production":
            reason = "dev_live_disabled"
        elif not config_enabled:
            reason = "live_reads_disabled_by_config"
        elif not confirm:
            reason = "confirmation_required"
        else:
            reason = None

        if reason is not None:
            return {
                "surface": "analytics.sources.refresh.live",
                "status": "blocked",
                "live_read_performed": False,
                "reason": reason,
                "environment": environment,
                "config_enabled": config_enabled,
                "confirm_received": bool(confirm),
                "guardrails": {
                    "fail_closed": True,
                    "no_live_read_when_blocked": True,
                    "local_sqlite_only": True,
                },
                "message": (
                    "Live refresh is disabled in this environment. It requires production, "
                    "server config (enable_live_reads), and explicit confirmation."
                ),
            }

        allow_procore_live = bool(scheduler.enable_procore_live_reads)
        allow_graph_live = bool(scheduler.enable_graph_live_reads)
        options = RefreshOptions(
            **_BASE,
            apply=True,
            confirm=True,
            mock_data=False,
            allow_procore_live=allow_procore_live,
            allow_graph_live=allow_graph_live,
        )
        with _maybe_live_env(allow_procore_live):
            summary = self._orchestrator().run(options=options)
        summary["surface"] = "analytics.sources.refresh.live"
        return summary
