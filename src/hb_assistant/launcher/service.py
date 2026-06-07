"""LauncherService: build the per-environment process specs and start/status/stop.

Process specs are profile/config-derived. The concrete uvicorn/npm/MCP/scheduler
commands are overridable fallback defaults (not hardwired requirements) so future
packaging can change how each surface is launched without touching the lifecycle code.
Optional surfaces (backend/frontend) degrade to a skipped/unavailable status rather
than failing the launch.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from hb_assistant import __version__
from hb_assistant.launcher.models import ManagedProcessSpec
from hb_assistant.launcher.process_manager import ProcessManager
from hb_assistant.launcher.profiles import Profile
from hb_assistant.launcher.session_state import SessionState
from hb_assistant.source_refresh.orchestrator import _safe_git_sha


def _hb_executable() -> str:
    exe = shutil.which("hb-assistant")
    if exe:
        return exe
    sibling = Path(sys.executable).parent / "hb-assistant"
    return str(sibling) if sibling.exists() else "hb-assistant"


class LauncherService:
    """Starts/stops the managed processes for one environment Profile."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.manager = ProcessManager(profile)

    # -- spec construction (profile/config-driven, overridable fallbacks) ----------

    def _child_env(self) -> dict[str, str]:
        """Env for child processes so they resolve THIS profile's paths.

        Dev children get an HB_PA_CONFIG pointing at a dev config file so they resolve
        the isolated dev app-support root; production children inherit the current env.
        """
        if self.profile.environment != "dev":
            return {}
        cfg_path = self.profile.app_support_root / "launcher-dev-config.yml"
        if not cfg_path.exists():
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            vault = self.profile.path_policy.get_vault_root()
            cfg_path.write_text(
                "paths:\n"
                f"  application_support_root: {self.profile.app_support_root}\n"
                f"  obsidian_vault: {vault}\n"
            )
        return {"HB_PA_CONFIG": str(cfg_path)}

    def build_specs(self) -> list[ManagedProcessSpec]:
        repo_root = str(self.profile.path_policy.resolve_repo_root())
        env = self._child_env()
        hb = _hb_executable()
        specs: list[ManagedProcessSpec] = []

        backend_port = self.profile.backend_port
        frontend_port = self.profile.frontend_port

        # Backend API (optional; analytics-ui extra). UI-independent service.
        specs.append(
            ManagedProcessSpec(
                name="backend",
                argv=[
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "hb_assistant.construction.analytics.api:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(backend_port),
                ],
                cwd=repo_root,
                env=env,
                enabled=True,
                keep_in_background=True,
                optional=True,
                port=backend_port,
            )
        )

        # Frontend (UI surface; terminated on Run-in-Background). Dev pins the Vite
        # port with --strictPort so it binds exactly frontend_port or exits (no drift).
        frontend_dir = Path(repo_root) / "frontend"
        if self.profile.environment == "dev" and shutil.which("npm"):
            specs.append(
                ManagedProcessSpec(
                    name="frontend",
                    argv=[
                        "npm",
                        "run",
                        "dev",
                        "--",
                        "--port",
                        str(frontend_port),
                        "--strictPort",
                        "--host",
                        "127.0.0.1",
                    ],
                    cwd=str(frontend_dir),
                    env=env,
                    enabled=frontend_dir.exists(),
                    keep_in_background=False,
                    optional=True,
                    port=frontend_port,
                )
            )
        else:
            dist = frontend_dir / "dist"
            specs.append(
                ManagedProcessSpec(
                    name="frontend",
                    argv=[
                        sys.executable,
                        "-m",
                        "http.server",
                        str(frontend_port),
                        "--directory",
                        str(dist),
                    ],
                    cwd=repo_root,
                    env=env,
                    enabled=dist.exists(),
                    keep_in_background=False,
                    optional=True,
                    port=frontend_port,
                )
            )

        # MCP stdio server (background service).
        specs.append(
            ManagedProcessSpec(
                name="mcp",
                argv=[hb, "second-brain", "mcp", "serve", "--stdio"],
                cwd=repo_root,
                env=env,
                enabled=True,
                keep_in_background=True,
                optional=True,
            )
        )

        # Foreground scheduler runner (background service; OS backends use this same runner).
        specs.append(
            ManagedProcessSpec(
                name="scheduler",
                argv=[
                    hb,
                    "scheduler",
                    "run",
                    "daily-source-refresh",
                    "--environment",
                    self.profile.environment,
                    "--loop",
                ],
                cwd=repo_root,
                env=env,
                enabled=self.profile.scheduler_enabled,
                keep_in_background=True,
                optional=False,
            )
        )
        return specs

    # -- lifecycle ----------------------------------------------------------------

    def start(self, *, plan_only: bool = False, force_restart: bool = False) -> dict[str, Any]:
        preflight_block: dict[str, Any] | None = None
        if not plan_only:
            from hb_assistant.launcher.preflight import run_preflight

            pf = run_preflight(
                self.profile,
                self.manager,
                force_restart=force_restart,
                required_ports=[
                    ("backend", self.profile.backend_port),
                    ("frontend", self.profile.frontend_port),
                ],
            )
            preflight_block = pf.to_dict()
            if not pf.ok:
                result = self.status(reconcile=True)
                result["command"] = "launcher start"
                result["status"] = "port_conflict"
                result["port_conflicts"] = pf.conflicts
                result["preflight"] = preflight_block
                return result
            if pf.reused:
                result = self.status(reconcile=True)
                result["reused"] = True
                result["preflight"] = preflight_block
                return result

        state = self.manager.load_session()
        records = []
        for spec in self.build_specs():
            if not spec.enabled:
                records.append(self.manager.planned(spec, reason="disabled"))
                records[-1].status = "skipped"
                records[-1].reason = "disabled_or_unavailable"
                continue
            if plan_only:
                records.append(self.manager.planned(spec))
            else:
                records.append(self.manager.spawn(spec))
        state.processes = records
        state.background_active = False
        state.frontend_url = self.profile.frontend_url
        self.manager.save_session(state)
        result = self.status(reconcile=not plan_only)
        if preflight_block is not None:
            result["preflight"] = preflight_block
        return result

    def open_session(
        self,
        *,
        shell: str = "browser",
        open_timeout_seconds: int | None = None,
        frontend_url: str | None = None,
        plan_only: bool = False,
        force_restart: bool = False,
    ) -> dict[str, Any]:
        """Start the session, wait for the frontend, then open it (browser/pywebview).

        Resolution order for the URL: explicit ``frontend_url`` (CLI override) →
        the profile's resolved ``frontend_url`` (config/fallback). Browser mode cannot
        intercept window-close, so it reports ``window_close_intercept_supported=false``
        and defers Quit / Run-in-Background to the ``launcher close`` commands.
        """
        from hb_assistant.launcher.frontend_open import open_browser, wait_for_frontend

        if frontend_url:
            url, url_source = frontend_url, "cli"
        else:
            url, url_source = self.profile.frontend_url, self.profile.frontend_url_source
        timeout = (
            open_timeout_seconds
            if open_timeout_seconds is not None
            else self.profile.frontend_open_timeout_seconds
        )

        result = self.start(plan_only=plan_only, force_restart=force_restart)

        # Preflight refused to start (unknown process on a required port): do not
        # open a browser onto a conflicting/duplicate session — surface and stop.
        if result.get("status") == "port_conflict":
            return result

        warnings: list[str] = []
        # 1. Health-check the routable URL (this is what readiness always tracks).
        reachable, wait_warnings = wait_for_frontend(url, timeout_seconds=timeout)
        warnings.extend(wait_warnings)

        # 2-5. Optional display alias: open the friendlier URL only when it resolves.
        alias_url = self.profile.frontend_alias_url
        display_name = self.profile.frontend_display_name
        if alias_url:
            alias_ok, _alias_warn = wait_for_frontend(alias_url, timeout_seconds=min(timeout, 5))
            if alias_ok:
                opened_url, alias_resolution_status = alias_url, "resolved"
            else:
                opened_url, alias_resolution_status = url, "unreachable"
                warnings.append(
                    f"frontend_alias_url {alias_url} not reachable; "
                    f"opening routable frontend_url {url} instead"
                )
        else:
            opened_url, alias_resolution_status = url, "not_configured"

        requested_shell = shell
        actual_shell = shell
        open_method = shell
        intercept_supported = False
        opened = False

        if shell == "pywebview":
            from hb_assistant.launcher.webview_shell import pywebview_available

            if pywebview_available():
                # pywebview manages its own window + close interception; surface that
                # without blocking here (the interactive shell is launched separately).
                intercept_supported = True
                open_method = "pywebview"
                actual_shell = "pywebview"
                opened = True
            else:
                actual_shell = "browser"
                open_method = "browser_fallback"
                warnings.append(
                    "pywebview requested but not installed; falling back to default browser. "
                    "Window-close interception is unavailable in browser mode."
                )
                opened, _method, open_warnings = open_browser(opened_url)
                warnings.extend(open_warnings)
        else:
            opened, open_method, open_warnings = open_browser(opened_url)
            warnings.extend(open_warnings)

        # Persist the resolved URLs + last-open outcome so `status` can report them.
        state = self.manager.load_session()
        state.frontend_url = url
        state.frontend_display_name = display_name
        state.frontend_alias_url = alias_url
        state.opened_url = opened_url
        state.alias_resolution_status = alias_resolution_status
        state.last_open_warnings = warnings
        self.manager.save_session(state)

        result.update(
            {
                "command": "launcher open",
                "frontend_display_name": display_name,
                "frontend_url": url,
                "frontend_alias_url": alias_url,
                "opened_url": opened_url,
                "frontend_url_source": url_source,
                "alias_resolution_status": alias_resolution_status,
                "frontend_reachable": reachable,
                "frontend_opened": opened,
                "open_method": open_method,
                "requested_shell": requested_shell,
                "actual_shell": actual_shell,
                "timeout_seconds": timeout,
                "window_close_intercept_supported": intercept_supported,
                "lifecycle_control": (
                    "pywebview_window" if intercept_supported else "cli_or_ui_action_required"
                ),
                "warnings": warnings,
            }
        )
        return result

    def stop(self) -> dict[str, Any]:
        state = self.manager.load_session()
        stopped = []
        for rec in state.processes:
            rec.status = self.manager.terminate(rec)
            stopped.append(rec.name)
        state.processes = []
        state.background_active = False
        self.manager.save_session(state)
        return {
            "command": "launcher stop",
            "environment": self.profile.environment,
            "stopped": stopped,
            "status": "ok",
        }

    def status(self, *, reconcile: bool = True) -> dict[str, Any]:
        state = self.manager.load_session()
        if reconcile:
            state = self.manager.reconcile(state)
            self.manager.save_session(state)
        return {
            "command": "launcher status",
            "environment": self.profile.environment,
            "environment_mode": self.profile.environment,
            "app_version": __version__,
            "build_sha": _safe_git_sha(),
            "executable_path": _hb_executable(),
            "python_path": sys.executable,
            "config_profile": self.profile.environment,
            "db_path": self.profile.summary()["db_path"],
            "log_path": self.profile.summary()["log_path"],
            "background_mode_active": state.background_active,
            "frontend_display_name": self.profile.frontend_display_name,
            "frontend_url": state.frontend_url or self.profile.frontend_url,
            "frontend_alias_url": self.profile.frontend_alias_url,
            "frontend_port": self.profile.frontend_port,
            "backend_port": self.profile.backend_port,
            "opened_url": state.opened_url,
            "frontend_url_source": self.profile.frontend_url_source,
            "alias_resolution_status": state.alias_resolution_status,
            "warnings": state.last_open_warnings,
            "processes": [r.model_dump() for r in state.processes],
            "backend_status": _proc_status(state, "backend"),
            "frontend_status": _proc_status(state, "frontend"),
            "mcp_status": _proc_status(state, "mcp"),
            "scheduler_status": _proc_status(state, "scheduler"),
            "profile": self.profile.summary(),
            "status": "ok",
        }


def _proc_status(state: SessionState, name: str) -> str:
    for rec in state.processes:
        if rec.name == name:
            return rec.status
    return "not_started"
