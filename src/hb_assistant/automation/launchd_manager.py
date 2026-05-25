"""LaunchdManager: render, install, manage macOS user LaunchAgent for morning automation (Phase 12).

Uses plistlib for safe XML handling (robust, no shell sed).
Respects config (MorningRunConfig for time, paths via PathPolicy for logs/venv/app root).
Supports --dry-run (preview only).
launchctl calls are subprocess, output sanitized (no tokens).
"""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from hb_assistant.config.loader import load_config
from hb_assistant.config.models import MorningRunConfig
from hb_assistant.config.path_policy import PathPolicy


class LaunchdManager:
    """Manages the com.hb.personal-assistant.morning LaunchAgent."""

    LABEL = "com.hb.personal-assistant.morning"

    def __init__(self, path_policy: Optional[PathPolicy] = None):
        self.pp = path_policy or PathPolicy()
        self.cfg = load_config().automation.morning_run
        self.launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        self.plist_path = self.launch_agents_dir / f"{self.LABEL}.plist"

    def _parse_time(self, time_str: str) -> tuple[int, int]:
        """Parse HH:MM to (hour, minute)."""
        try:
            h, m = map(int, time_str.split(":"))
            return max(0, min(23, h)), max(0, min(59, m))
        except Exception:
            return 5, 0  # safe default

    def render_plist(self) -> Dict[str, Any]:
        """Build the plist dict from config + paths (no file I/O for the template at runtime)."""
        hour, minute = self._parse_time(self.cfg.time)
        venv_python = str(self.pp.get_app_support().parent / ".venv" / "bin" / "hb-assistant")  # heuristic; user can override via dry-run preview
        # Prefer the actual console script path if detectable; fallback is documented
        # For real install we use the venv from PathPolicy app support convention
        app_root = str(self.pp.get_app_support().parent)  # project root assumption for working dir

        # Log paths per spec/example
        logs_dir = self.pp.get_logs_dir()
        out_log = logs_dir / "run-logs" / "launchd-morning.out.log"
        err_log = logs_dir / "error-logs" / "launchd-morning.err.log"

        plist: Dict[str, Any] = {
            "Label": self.LABEL,
            "ProgramArguments": [
                venv_python,
                "run",
                "morning",
            ],
            "WorkingDirectory": app_root,
            "StartCalendarInterval": {"Hour": hour, "Minute": minute},
            "StandardOutPath": str(out_log),
            "StandardErrorPath": str(err_log),
            "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
            # KeepAlive false; calendar driven
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
        """Dry-run safe preview: returns the would-be plist + commands (sanitized paths)."""
        data = self.render_plist()
        # Redact ~ home for evidence friendliness
        redacted = str(self.plist_path).replace(str(Path.home()), "~")
        return {
            "action": "preview_install",
            "label": self.LABEL,
            "plist_path": redacted,
            "plist": data,
            "commands": [
                f"launchctl load -w {redacted}",
                "launchctl kickstart -k gui/$(id -u)/" + self.LABEL,
            ],
            "note": "Dry-run only. Real install uses launchctl on the written plist.",
        }

    def install(self, dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            return self.preview_install()

        data = self.render_plist()
        self.ensure_log_dirs()
        written = self._write_plist(data)

        # load
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
            "label": self.LABEL,
            "plist_path": str(written).replace(str(Path.home()), "~"),
            "status": status,
        }

    def uninstall(self, dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            redacted = str(self.plist_path).replace(str(Path.home()), "~")
            return {
                "action": "preview_uninstall",
                "label": self.LABEL,
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

        return {"action": "uninstall", "label": self.LABEL, "status": status}

    def kickstart(self) -> Dict[str, Any]:
        """Force immediate run (for testing)."""
        try:
            uid = subprocess.check_output(["id", "-u"], text=True).strip()
            out = subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{self.LABEL}"],
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

        return {
            "label": self.LABEL,
            "plist_exists": exists,
            "plist_path": redacted_path,
            "config_time": self.cfg.time,
            "weekend_behavior": self.cfg.weekend_behavior,
            "catch_up": self.cfg.catch_up_if_machine_wakes_after,
            "last_run_from_ledger": last_run,
        }
