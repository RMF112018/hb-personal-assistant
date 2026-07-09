"""PREVIEW-ONLY launchd job builder for the periodic ``source-structure refresh`` cycle.

Mirrors the plist shape of :class:`~hb_assistant.automation.launchd_manager.LaunchdManager` but is
deliberately install-free: it renders the plist / job definition for operator review and NEVER calls
``launchctl load``/``bootstrap``. Actual install remains a separate, future operator command. The
returned ``commands`` are informational strings only — nothing here executes them.
"""

from __future__ import annotations

import plistlib
import shutil
import sys
from pathlib import Path
from typing import Any

from hb_assistant.config.models import SourceStructureScheduleConfig


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM to (hour, minute); fall back to 03:00 on malformed input."""
    try:
        h, m = map(int, time_str.split(":"))
        return max(0, min(23, h)), max(0, min(59, m))
    except Exception:
        return 3, 0


def _resolve_executable() -> Path:
    discovered = shutil.which("hb-assistant")
    if discovered:
        return Path(discovered)
    sibling = Path(sys.executable).resolve().parent / "hb-assistant"
    return sibling if sibling.exists() else Path("hb-assistant")


def build_refresh_job(
    schedule: SourceStructureScheduleConfig,
    *,
    output_root: str,
    executable_path: str | None = None,
    working_directory: str | None = None,
) -> dict[str, Any]:
    """Build (never install) the launchd job definition for ``source-structure refresh``.

    Returns the label, the plist dict, its rendered XML, the (informational-only) launchctl commands,
    and the enabled flag. No side effects: no file is written and ``launchctl`` is never invoked.
    """
    hour, minute = _parse_time(schedule.schedule_time)
    executable = Path(executable_path).expanduser() if executable_path else _resolve_executable()
    working_dir = Path(working_directory).expanduser() if working_directory else Path.cwd()

    program_arguments = [
        str(executable), "source-structure", "refresh",
        "--apply", "--output-root", output_root,
    ]
    plist: dict[str, Any] = {
        "Label": schedule.label,
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(working_dir),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }
    home = str(Path.home())
    redacted_label_path = f"~/Library/LaunchAgents/{schedule.label}.plist"
    return {
        "action": "preview_only",
        "enabled": schedule.enabled,
        "label": schedule.label,
        "plist": plist,
        "plist_xml": plistlib.dumps(plist).decode("utf-8"),
        "program_arguments": program_arguments,
        "schedule_time": f"{hour:02d}:{minute:02d}",
        # Informational only — a future operator command runs these; this builder never does.
        "install_commands": [
            f"launchctl load -w {redacted_label_path}",
        ],
        "note": ("PREVIEW ONLY — no plist written, launchctl never invoked. Enable "
                 "source_structure.schedule.enabled and run a future operator install command to load."),
        "working_directory": str(working_dir).replace(home, "~"),
    }
