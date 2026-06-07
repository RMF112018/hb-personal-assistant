"""Foreground-loop fallback backend (cross-platform, no OS artifact).

There is no native scheduler artifact: a long-running process repeatedly calls the
runner's `tick`. The same app-level `due`/state logic owns catch-up, so the loop is
safe to start/stop at any time and never double-runs a schedule date.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.scheduler.models import InstallPlan


class ForegroundLoopBackend:
    def __init__(self, plan: InstallPlan) -> None:
        self.plan = plan
        self.loop_argv = [
            self.plan.executable,
            "scheduler",
            "run",
            self.plan.job_id,
            "--environment",
            self.plan.environment,
            "--loop",
        ]
        if plan.mock_data:
            self.loop_argv.append("--mock-data")

    def preview(self) -> dict[str, Any]:
        return {
            "backend": "foreground",
            "action": "preview",
            "loop_argv": self.loop_argv,
            "schedule_time_local": self.plan.schedule_time_local,
            "writes_files": False,
            "note": "No OS artifact; run the loop via the launcher or `scheduler run --loop`.",
        }

    def install(self, *, dry_run: bool) -> dict[str, Any]:
        # Nothing to install on the OS; the loop is launched as a managed process.
        return {**self.preview(), "action": "install", "dry_run": dry_run, "installed": False}

    def uninstall(self, *, dry_run: bool) -> dict[str, Any]:
        return {
            "backend": "foreground",
            "action": "uninstall",
            "removed": False,
            "dry_run": dry_run,
        }

    def status(self) -> dict[str, Any]:
        return {"backend": "foreground", "installed": False, "loop_argv": self.loop_argv}
