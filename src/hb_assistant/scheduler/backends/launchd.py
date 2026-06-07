"""macOS launchd LaunchAgent backend for the daily source-refresh scheduler."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from typing import Any

from hb_assistant.scheduler.models import InstallPlan


class LaunchdSchedulerBackend:
    def __init__(self, plan: InstallPlan, *, log_path: Path) -> None:
        self.plan = plan
        self.log_path = log_path
        self.plist_path = Path.home() / "Library" / "LaunchAgents" / f"{plan.label}.plist"

    def render_plist(self) -> dict[str, Any]:
        hh, mm = (int(x) for x in self.plan.schedule_time_local.split(":", 1))
        return {
            "Label": self.plan.label,
            "ProgramArguments": self.plan.runner_argv,
            "WorkingDirectory": self.plan.working_directory,
            "StartCalendarInterval": {"Hour": hh, "Minute": mm},
            "StandardOutPath": str(self.log_path / "scheduler.out.log"),
            "StandardErrorPath": str(self.log_path / "scheduler.err.log"),
            "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        }

    def preview(self) -> dict[str, Any]:
        return {
            "backend": "launchd",
            "action": "preview",
            "plist_path": str(self.plist_path),
            "plist": self.render_plist(),
            "writes_files": False,
        }

    def install(self, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {**self.preview(), "dry_run": True, "installed": False}
        self.plist_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.mkdir(parents=True, exist_ok=True)
        with self.plist_path.open("wb") as fh:
            plistlib.dump(self.render_plist(), fh)
        rc = subprocess.run(  # noqa: S603,S607
            ["launchctl", "load", "-w", str(self.plist_path)], capture_output=True, check=False
        )
        return {
            "backend": "launchd",
            "action": "install",
            "installed": True,
            "plist_path": str(self.plist_path),
            "launchctl_rc": rc.returncode,
            "dry_run": False,
        }

    def uninstall(self, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {"backend": "launchd", "action": "uninstall", "dry_run": True, "removed": False}
        if self.plist_path.exists():
            subprocess.run(  # noqa: S603,S607
                ["launchctl", "unload", "-w", str(self.plist_path)],
                capture_output=True,
                check=False,
            )
            self.plist_path.unlink()
        return {"backend": "launchd", "action": "uninstall", "removed": True, "dry_run": False}

    def status(self) -> dict[str, Any]:
        return {
            "backend": "launchd",
            "installed": self.plist_path.exists(),
            "plist_path": str(self.plist_path),
            "schedule_time_local": self.plan.schedule_time_local,
        }
