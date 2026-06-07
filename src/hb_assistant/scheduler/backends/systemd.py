"""Linux systemd user service+timer backend for the daily source-refresh scheduler."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from hb_assistant.scheduler.models import InstallPlan


class SystemdBackend:
    def __init__(self, plan: InstallPlan) -> None:
        self.plan = plan
        self.unit = f"hb-pa-scheduler-{plan.environment}"
        self.unit_dir = Path.home() / ".config" / "systemd" / "user"
        self.service_path = self.unit_dir / f"{self.unit}.service"
        self.timer_path = self.unit_dir / f"{self.unit}.timer"

    def render_service(self) -> str:
        exec_start = " ".join(self.plan.runner_argv)
        return (
            "[Unit]\n"
            "Description=HB Assistant daily source refresh "
            f"({self.plan.environment})\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"WorkingDirectory={self.plan.working_directory}\n"
            f"ExecStart={exec_start}\n"
        )

    def render_timer(self) -> str:
        persistent = "true" if self.plan.catch_up_on_wake else "false"
        return (
            "[Unit]\n"
            "Description=HB Assistant daily source refresh timer "
            f"({self.plan.environment})\n\n"
            "[Timer]\n"
            f"OnCalendar=*-*-* {self.plan.schedule_time_local}:00\n"
            f"Persistent={persistent}\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        )

    def preview(self) -> dict[str, Any]:
        return {
            "backend": "systemd",
            "action": "preview",
            "service_path": str(self.service_path),
            "timer_path": str(self.timer_path),
            "service": self.render_service(),
            "timer": self.render_timer(),
            "writes_files": False,
        }

    def install(self, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {**self.preview(), "dry_run": True, "installed": False}
        self.unit_dir.mkdir(parents=True, exist_ok=True)
        self.service_path.write_text(self.render_service())
        self.timer_path.write_text(self.render_timer())
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, check=False)  # noqa: S603,S607
        rc = subprocess.run(  # noqa: S603,S607
            ["systemctl", "--user", "enable", "--now", f"{self.unit}.timer"],
            capture_output=True,
            check=False,
        )
        return {
            "backend": "systemd",
            "action": "install",
            "installed": True,
            "unit": self.unit,
            "systemctl_rc": rc.returncode,
            "dry_run": False,
        }

    def uninstall(self, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {"backend": "systemd", "action": "uninstall", "dry_run": True, "removed": False}
        subprocess.run(  # noqa: S603,S607
            ["systemctl", "--user", "disable", "--now", f"{self.unit}.timer"],
            capture_output=True,
            check=False,
        )
        for p in (self.service_path, self.timer_path):
            if p.exists():
                p.unlink()
        return {"backend": "systemd", "action": "uninstall", "removed": True, "dry_run": False}

    def status(self) -> dict[str, Any]:
        return {
            "backend": "systemd",
            "unit": self.unit,
            "installed": self.timer_path.exists(),
            "timer_path": str(self.timer_path),
            "schedule_time_local": self.plan.schedule_time_local,
        }
