"""LaunchdManager: render, install, manage macOS user LaunchAgent for morning automation.

Renders LaunchAgent plist with verified executable + working directory and
provides dry-run readiness diagnostics before install.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from hb_assistant.config.loader import load_config
from hb_assistant.config.models import LaunchdConfig, MorningRunConfig
from hb_assistant.config.path_policy import PathPolicy


class LaunchdManager:
    """Manages the com.hb.personal-assistant.morning LaunchAgent."""

    DEFAULT_LABEL = "com.hb.personal-assistant.morning"

    def __init__(self, path_policy: Optional[PathPolicy] = None):
        self.pp = path_policy or PathPolicy()
        automation_cfg = load_config().automation
        self.cfg: MorningRunConfig = automation_cfg.morning_run
        self.launchd_cfg: LaunchdConfig = automation_cfg.launchd
        self.label = self.launchd_cfg.label or self.DEFAULT_LABEL
        self.launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        self.plist_path = self.launch_agents_dir / f"{self.label}.plist"

    def _parse_time(self, time_str: str) -> tuple[int, int]:
        """Parse HH:MM to (hour, minute)."""
        try:
            h, m = map(int, time_str.split(":"))
            return max(0, min(23, h)), max(0, min(59, m))
        except Exception:
            return 5, 0

    def _resolve_executable_path(self) -> Path:
        """Resolve CLI executable path from config, console script, then runtime fallback."""
        if self.launchd_cfg.executable_path:
            return Path(self.launchd_cfg.executable_path).expanduser()

        discovered = shutil.which("hb-assistant")
        if discovered:
            return Path(discovered)

        if self.launchd_cfg.python_path:
            py = Path(self.launchd_cfg.python_path).expanduser()
            sibling = py.parent / "hb-assistant"
            if sibling.exists():
                return sibling

        runtime = Path(sys.executable).resolve()
        sibling = runtime.parent / "hb-assistant"
        if sibling.exists():
            return sibling

        return Path("hb-assistant")

    def _resolve_working_directory(self) -> Path:
        """Resolve working directory from config or repo root."""
        if self.launchd_cfg.working_directory:
            return Path(self.launchd_cfg.working_directory).expanduser()
        return self.pp.resolve_repo_root()

    def _command_grammar_valid(self, program_args: list[str]) -> bool:
        return len(program_args) == 3 and program_args[1] == "run" and program_args[2] == "morning"

    def _readiness(self, executable: Path, working_dir: Path, program_args: list[str]) -> Dict[str, Any]:
        self.ensure_log_dirs()
        logs_dir = self.pp.get_logs_dir()

        executable_exists = executable.exists()
        executable_is_file = executable.is_file()
        executable_is_executable = os.access(executable, os.X_OK) if executable_exists else False

        working_directory_exists = working_dir.exists()
        working_directory_is_dir = working_dir.is_dir()

        run_log_dir = logs_dir / "run-logs"
        err_log_dir = logs_dir / "error-logs"
        log_dirs_writable = os.access(run_log_dir, os.W_OK) and os.access(err_log_dir, os.W_OK)

        command_grammar_valid = self._command_grammar_valid(program_args)
        blocking = not (
            executable_exists
            and executable_is_file
            and executable_is_executable
            and working_directory_exists
            and working_directory_is_dir
            and command_grammar_valid
            and log_dirs_writable
        )

        return {
            "executable_exists": executable_exists,
            "executable_is_file": executable_is_file,
            "executable_is_executable": executable_is_executable,
            "working_directory_exists": working_directory_exists,
            "working_directory_is_directory": working_directory_is_dir,
            "command_grammar_valid": command_grammar_valid,
            "log_directories_writable": log_dirs_writable,
            "plist_path": str(self.plist_path).replace(str(Path.home()), "~"),
            "blocking": blocking,
            "ready": not blocking,
        }

    def render_plist(self) -> Dict[str, Any]:
        """Build plist dict from resolved executable/working directory + config time/logs."""
        hour, minute = self._parse_time(self.cfg.time)
        executable = self._resolve_executable_path()
        working_dir = self._resolve_working_directory()

        logs_dir = self.pp.get_logs_dir()
        out_log = logs_dir / "run-logs" / "launchd-morning.out.log"
        err_log = logs_dir / "error-logs" / "launchd-morning.err.log"

        plist: Dict[str, Any] = {
            "Label": self.label,
            "ProgramArguments": [str(executable), "run", "morning"],
            "WorkingDirectory": str(working_dir),
            "StartCalendarInterval": {"Hour": hour, "Minute": minute},
            "StandardOutPath": str(out_log),
            "StandardErrorPath": str(err_log),
            "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        }
        return plist

    def ensure_log_dirs(self) -> None:
        logs = self.pp.get_logs_dir()
        (logs / "run-logs").mkdir(parents=True, exist_ok=True)
        (logs / "error-logs").mkdir(parents=True, exist_ok=True)

    def _write_plist(self, data: Dict[str, Any]) -> Path:
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        with self.plist_path.open("wb") as f:
            plistlib.dump(data, f)
        return self.plist_path

    def preview_install(self) -> Dict[str, Any]:
        """Dry-run preview with explicit readiness and blocking diagnostics."""
        data = self.render_plist()
        executable = Path(data["ProgramArguments"][0])
        working_dir = Path(data["WorkingDirectory"])
        readiness = self._readiness(executable, working_dir, data["ProgramArguments"])

        redacted = str(self.plist_path).replace(str(Path.home()), "~")
        result = {
            "action": "preview_install",
            "label": self.label,
            "plist_path": redacted,
            "plist": data,
            "readiness": readiness,
            "commands": [
                f"launchctl load -w {redacted}",
                "launchctl kickstart -k gui/$(id -u)/" + self.label,
            ],
            "note": "Dry-run only. Real install uses launchctl on the written plist.",
        }
        if readiness["blocking"]:
            result["status"] = "blocking_diagnostic"
        else:
            result["status"] = "ready"
        return result

    def install(self, dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            return self.preview_install()

        preview = self.preview_install()
        if preview["readiness"].get("blocking", False):
            return {
                "action": "install",
                "label": self.label,
                "status": "blocked",
                "readiness": preview["readiness"],
                "message": "Launchd install blocked: executable/working directory readiness failed.",
            }

        data = preview["plist"]
        written = self._write_plist(data)

        try:
            subprocess.run(
                ["launchctl", "load", "-w", str(written)],
                check=True,
                capture_output=True,
                text=True,
            )
            status = "loaded"
        except subprocess.CalledProcessError as e:
            status = f"load_failed: {e.stderr[:200] if e.stderr else str(e)}"

        return {
            "action": "install",
            "label": self.label,
            "plist_path": str(written).replace(str(Path.home()), "~"),
            "status": status,
        }

    def uninstall(self, dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            redacted = str(self.plist_path).replace(str(Path.home()), "~")
            return {
                "action": "preview_uninstall",
                "label": self.label,
                "plist_path": redacted,
                "commands": [f"launchctl unload -w {redacted}", f"rm -f {redacted}"],
            }

        if self.plist_path.exists():
            try:
                subprocess.run(
                    ["launchctl", "unload", "-w", str(self.plist_path)],
                    check=False,
                    capture_output=True,
                )
            except Exception:
                pass
            try:
                self.plist_path.unlink()
            except Exception:
                pass
            status = "uninstalled"
        else:
            status = "no_plist"

        return {"action": "uninstall", "label": self.label, "status": status}

    def kickstart(self) -> Dict[str, Any]:
        """Force immediate run (for testing)."""
        try:
            uid = subprocess.check_output(["id", "-u"], text=True).strip()
            out = subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{self.label}"],
                capture_output=True,
                text=True,
            )
            return {"action": "kickstart", "status": "ok", "stdout": out.stdout[:500], "stderr": out.stderr[:500]}
        except Exception as e:
            return {"action": "kickstart", "status": f"error: {str(e)[:200]}"}

    def status(self) -> Dict[str, Any]:
        """Return sanitized status for diagnostics (no secrets)."""
        exists = self.plist_path.exists()
        redacted_path = str(self.plist_path).replace(str(Path.home()), "~") if exists else None
        last_run = None
        try:
            from hb_assistant.store.repositories import Store

            s = Store()
            summary = s.get_summary()
            last_run = summary.get("last_run")
        except Exception:
            pass

        plist = self.render_plist()
        readiness = self._readiness(Path(plist["ProgramArguments"][0]), Path(plist["WorkingDirectory"]), plist["ProgramArguments"])

        return {
            "label": self.label,
            "plist_exists": exists,
            "plist_path": redacted_path,
            "config_time": self.cfg.time,
            "weekend_behavior": self.cfg.weekend_behavior,
            "catch_up": self.cfg.catch_up_if_machine_wakes_after,
            "last_run_from_ledger": last_run,
            "program_arguments": plist["ProgramArguments"],
            "working_directory": plist["WorkingDirectory"],
            "readiness": readiness,
        }
