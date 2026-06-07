"""Windows Task Scheduler backend for the daily source-refresh scheduler."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from hb_assistant.scheduler.models import InstallPlan


class WindowsTaskBackend:
    def __init__(self, plan: InstallPlan, *, state_dir: Path) -> None:
        self.plan = plan
        self.state_dir = state_dir
        self.task_name = f"HB-PA-Scheduler-{plan.environment}"
        self.xml_path = state_dir / f"task-{plan.environment}.xml"

    def render_xml(self) -> str:
        cmd = self.plan.runner_argv[0]
        args = " ".join(self.plan.runner_argv[1:])
        start = f"2026-01-01T{self.plan.schedule_time_local}:00"
        return (
            '<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" '
            'xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            "  <Triggers>\n"
            "    <CalendarTrigger>\n"
            f"      <StartBoundary>{start}</StartBoundary>\n"
            "      <Enabled>true</Enabled>\n"
            "      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>\n"
            "    </CalendarTrigger>\n"
            "  </Triggers>\n"
            "  <Settings>\n"
            "    <StartWhenAvailable>true</StartWhenAvailable>\n"
            "    <WakeToRun>false</WakeToRun>\n"
            "  </Settings>\n"
            "  <Actions>\n"
            "    <Exec>\n"
            f"      <Command>{cmd}</Command>\n"
            f"      <Arguments>{args}</Arguments>\n"
            f"      <WorkingDirectory>{self.plan.working_directory}</WorkingDirectory>\n"
            "    </Exec>\n"
            "  </Actions>\n"
            "</Task>\n"
        )

    def _schtasks_create_argv(self) -> list[str]:
        return ["schtasks", "/Create", "/TN", self.task_name, "/XML", str(self.xml_path), "/F"]

    def preview(self) -> dict[str, Any]:
        return {
            "backend": "windows",
            "action": "preview",
            "task_name": self.task_name,
            "xml_path": str(self.xml_path),
            "xml": self.render_xml(),
            "schtasks_argv": self._schtasks_create_argv(),
            "writes_files": False,
        }

    def install(self, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {**self.preview(), "dry_run": True, "installed": False}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.xml_path.write_text(self.render_xml(), encoding="utf-16")
        rc = subprocess.run(self._schtasks_create_argv(), capture_output=True, check=False)  # noqa: S603
        return {
            "backend": "windows",
            "action": "install",
            "installed": True,
            "task_name": self.task_name,
            "schtasks_rc": rc.returncode,
            "dry_run": False,
        }

    def uninstall(self, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {"backend": "windows", "action": "uninstall", "dry_run": True, "removed": False}
        subprocess.run(  # noqa: S603,S607
            ["schtasks", "/Delete", "/TN", self.task_name, "/F"], capture_output=True, check=False
        )
        if self.xml_path.exists():
            self.xml_path.unlink()
        return {"backend": "windows", "action": "uninstall", "removed": True, "dry_run": False}

    def status(self) -> dict[str, Any]:
        return {
            "backend": "windows",
            "task_name": self.task_name,
            "xml_path": str(self.xml_path),
            "installed": self.xml_path.exists(),
            "schedule_time_local": self.plan.schedule_time_local,
        }
