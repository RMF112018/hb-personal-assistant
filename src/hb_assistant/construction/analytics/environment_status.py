"""Environment + aggregate source-status service for the analytics UI shell.

Browser-safe, read-only, and fully offline: reports the runtime environment mode,
source-refresh mode, live-read flags, and a single Graph + Procore + scheduler/
freshness summary for the Dev/Production UI. It NEVER calls a live Graph or Procore
data client and NEVER shells out to the CLI.

Environment is inferred from the resolved Application Support root (which honors the
launcher's ``HB_PA_CONFIG`` signal via ``load_config()``). We deliberately do NOT
call ``launcher.profiles.resolve_profile`` here: inside the dev backend subprocess
``load_config()`` already returns the dev-rooted config, so ``resolve_profile`` would
re-append ``" (Dev)"`` and produce wrong paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy


def _redact(p: Path | str) -> str:
    """Replace the home prefix with ``~`` so no full home path leaks to the browser."""
    text = str(p)
    home = str(Path.home())
    return text.replace(home, "~") if text.startswith(home) else text


def _safe_guardrails() -> dict[str, Any]:
    # Single source of truth lives in api._guardrails(); import lazily to avoid any
    # import-time coupling, falling back to an equivalent literal if unavailable.
    try:
        from hb_assistant.construction.analytics.api import _guardrails

        return _guardrails()
    except Exception:
        return {
            "read_only": True,
            "local_first": True,
            "no_cli_shellout": True,
            "no_live_endpoint_calls": True,
            "no_external_writeback": True,
            "active_chat_routes": False,
            "chat_enabled": False,
        }


class EnvironmentStatusService:
    """Offline resolver for ``/api/environment`` and ``/api/sources/status``."""

    def __init__(self, *, path_policy: PathPolicy | None = None) -> None:
        self._config = load_config()
        self._pp = path_policy or PathPolicy(self._config)

    # --- environment / mode resolution (offline) ---

    def _environment(self) -> str:
        root = self._pp.get_app_support()
        return "dev" if root.name.endswith("(Dev)") else "production"

    def _source_refresh_mode(self, environment: str) -> str:
        # Mirrors launcher.profiles: dev is always local/mock; production may use
        # local or (explicitly gated) live reads.
        return "mock_data" if environment == "dev" else "local_or_gated_live"

    def _live_flags(self, environment: str) -> dict[str, Any]:
        scheduler = self._config.automation.scheduler
        try:
            from hb_assistant.procore.live_gate import live_env_active

            procore_live_env = bool(live_env_active())
        except Exception:
            procore_live_env = False

        live_reads = {
            "enable_live_reads": bool(scheduler.enable_live_reads),
            "enable_procore_live_reads": bool(scheduler.enable_procore_live_reads),
            "enable_graph_live_reads": bool(scheduler.enable_graph_live_reads),
            "procore_live_env_active": procore_live_env,
        }

        if environment == "dev":
            live_refresh = {
                "available": False,
                "enabled": False,
                "reason": "dev_local_mock_only",
            }
        elif scheduler.enable_live_reads:
            live_refresh = {
                "available": True,
                "enabled": True,
                "reason": "config_enabled",
            }
        else:
            live_refresh = {
                "available": False,
                "enabled": False,
                "reason": "live_reads_disabled_by_default",
            }
        return {"live_reads": live_reads, "live_refresh": live_refresh}

    def _launcher_env(self, environment: str) -> tuple[str, int, int]:
        """Return (frontend_url, frontend_port, backend_port) from launcher config."""
        launcher = self._config.launcher
        env_cfg = launcher.dev if environment == "dev" else launcher.production
        frontend_url = env_cfg.frontend_url or "http://127.0.0.1:5173"
        frontend_port = 5173
        try:
            from urllib.parse import urlparse

            parsed = urlparse(frontend_url).port
            frontend_port = int(parsed) if parsed else 5173
        except Exception:
            frontend_port = 5173
        return frontend_url, frontend_port, int(env_cfg.backend_port)

    # --- public builders (always return a dict; user-safe on failure) ---

    def build_environment(self) -> dict[str, Any]:
        environment = self._environment()
        flags = self._live_flags(environment)
        frontend_url, frontend_port, backend_port = self._launcher_env(environment)
        return {
            "surface": "analytics.environment",
            "status": "ok",
            "environment": environment,
            "source_refresh_mode": self._source_refresh_mode(environment),
            "frontend_url": frontend_url,
            "frontend_port": frontend_port,
            "backend_port": backend_port,
            "app_support_root": _redact(self._pp.get_app_support()),
            "live_reads": flags["live_reads"],
            "live_refresh": flags["live_refresh"],
            "guardrails": _safe_guardrails(),
        }

    def build_sources_status(self) -> dict[str, Any]:
        environment = self._environment()
        flags = self._live_flags(environment)
        return {
            "surface": "analytics.sources.status",
            "status": "ok",
            "environment": environment,
            "source_refresh_mode": self._source_refresh_mode(environment),
            "live_reads": flags["live_reads"],
            "live_refresh": flags["live_refresh"],
            "graph": self._graph_summary(),
            "procore": self._procore_summary(),
            "scheduler": self._scheduler_summary(environment),
            "guardrails": _safe_guardrails(),
        }

    # --- per-source summaries (offline, fail-closed to a safe "unavailable") ---

    def _combined_auth(self) -> dict[str, Any]:
        from hb_assistant.construction.analytics.auth_onboarding import AuthOnboardingService

        return AuthOnboardingService().build_combined_status()

    def _graph_summary(self) -> dict[str, Any]:
        try:
            graph = self._combined_auth().get("graph") or {}
            return {
                "system": "microsoft_365_graph",
                "token_type": graph.get("token_type"),
                "classification": graph.get("classification"),
                "account": graph.get("account"),
                "expires_in_seconds_if_known": graph.get("expires_in_seconds_if_known"),
            }
        except Exception:
            return {
                "system": "microsoft_365_graph",
                "status": "unavailable",
                "message": "Graph status could not be read locally.",
            }

    def _procore_summary(self) -> dict[str, Any]:
        try:
            procore = self._combined_auth().get("procore") or {}
            return {
                "system": "procore",
                "status": procore.get("status"),
                "cache_present": procore.get("cache_present"),
                "ready_for_live_calls": procore.get("ready_for_live_calls"),
                "expires_in_seconds_if_known": procore.get("expires_in_seconds_if_known"),
            }
        except Exception:
            return {
                "system": "procore",
                "status": "unavailable",
                "message": "Procore status could not be read locally.",
            }

    def _scheduler_summary(self, environment: str) -> dict[str, Any]:
        try:
            from hb_assistant.scheduler.state import SchedulerState

            state_path = (
                self._pp.get_app_support() / "scheduler-state" / "daily-source-refresh.json"
            )
            state = SchedulerState.load(state_path, environment=environment)
            return {
                "enabled": bool(self._config.automation.scheduler.enabled),
                "last_status": state.last_status,
                "last_successful_schedule_date": state.last_successful_schedule_date,
                "last_attempted_schedule_date": state.last_attempted_schedule_date,
                "consecutive_failures": state.consecutive_failures,
                "next_expected_run": state.next_expected_run,
                "schedule_time_local": state.schedule_time_local,
                "timezone": state.timezone,
                "live_reads_enabled": bool(self._config.automation.scheduler.enable_live_reads),
            }
        except Exception:
            return {
                "status": "unavailable",
                "message": "Scheduler state could not be read locally.",
            }
