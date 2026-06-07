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
                    "8000",
                ],
                cwd=repo_root,
                env=env,
                enabled=True,
                keep_in_background=True,
                optional=True,
            )
        )

        # Frontend (UI surface; terminated on Run-in-Background).
        frontend_dir = Path(repo_root) / "frontend"
        if self.profile.environment == "dev" and shutil.which("npm"):
            specs.append(
                ManagedProcessSpec(
                    name="frontend",
                    argv=["npm", "run", "dev"],
                    cwd=str(frontend_dir),
                    env=env,
                    enabled=frontend_dir.exists(),
                    keep_in_background=False,
                    optional=True,
                )
            )
        else:
            dist = frontend_dir / "dist"
            specs.append(
                ManagedProcessSpec(
                    name="frontend",
                    argv=[sys.executable, "-m", "http.server", "5173", "--directory", str(dist)],
                    cwd=repo_root,
                    env=env,
                    enabled=dist.exists(),
                    keep_in_background=False,
                    optional=True,
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

    def start(self, *, plan_only: bool = False) -> dict[str, Any]:
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
        state.frontend_url = "http://127.0.0.1:5173"
        self.manager.save_session(state)
        return self.status(reconcile=not plan_only)

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
            "frontend_url": state.frontend_url,
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
