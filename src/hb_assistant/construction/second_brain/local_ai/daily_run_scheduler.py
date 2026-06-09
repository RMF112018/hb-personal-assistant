"""Phase 10 Checkpoint 6 — dedicated launchd installer for the weekday 5:00 AM daily run.

A focused macOS LaunchAgent that fires ``second-brain daily-run run`` Monday–Friday at 05:00 local.
Modeled on :class:`hb_assistant.automation.launchd_manager.LaunchdManager` (plist rendering,
readiness diagnostics, dry-run preview) but kept separate so it never touches the Phase 12
``morning`` job.

Weekday-only is encoded as an **array** of five ``StartCalendarInterval`` entries (launchd Weekday
1=Mon … 5=Fri; no Sat/Sun entries). Catch-up is launchd-native: a missed weekday interval fires on
the next wake — the wrapper's date policy then resolves a weekend wake of a missed Friday to the
Friday brief, and skips a fresh weekend. Install/uninstall default to dry-run/plan (write nothing);
``--apply`` performs the real ``launchctl load``.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, Optional

from hb_assistant.config.path_policy import PathPolicy

DEFAULT_LABEL = "com.hb.personal-assistant.daily-local-agent"


class DailyRunLaunchdManager:
    """Renders + manages the weekday 5:00 AM daily-run LaunchAgent."""

    def __init__(
        self,
        *,
        time: str = "05:00",
        weekdays_only: bool = True,
        apply_mode: bool = True,
        max_persist_per_stage: int = 10,
        max_total_persist: int = 30,
        limit: int = 50,
        lookahead_days: int = 14,
        raw: bool = True,
        write_obsidian: bool = True,
        confirm_vault_write: bool = True,
        generate_browser: bool = True,
        timezone: str = "America/New_York",
        db_path: Optional[str] = None,
        include_relationship_candidates: bool = False,
        relationship_scan_threads: Optional[int] = None,
        relationship_scan_events: Optional[int] = None,
        label: str = DEFAULT_LABEL,
        path_policy: Optional[PathPolicy] = None,
    ) -> None:
        self.pp = path_policy or PathPolicy()
        self.time = time
        self.weekdays_only = weekdays_only
        self.apply_mode = apply_mode
        self.max_persist_per_stage = max_persist_per_stage
        self.max_total_persist = max_total_persist
        self.limit = limit
        self.lookahead_days = lookahead_days
        self.raw = raw
        self.write_obsidian = write_obsidian
        self.confirm_vault_write = confirm_vault_write
        self.generate_browser = generate_browser
        self.timezone = timezone
        self.db_path = db_path
        self.include_relationship_candidates = include_relationship_candidates
        self.relationship_scan_threads = relationship_scan_threads
        self.relationship_scan_events = relationship_scan_events
        self.label = label
        self.launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        self.plist_path = self.launch_agents_dir / f"{self.label}.plist"

    # --- plist construction ----------------------------------------------------

    def _parse_time(self, time_str: str) -> tuple[int, int]:
        try:
            h, m = map(int, time_str.split(":"))
            return max(0, min(23, h)), max(0, min(59, m))
        except Exception:
            return 5, 0

    def _resolve_executable_path(self) -> Path:
        discovered = shutil.which("hb-assistant")
        if discovered:
            return Path(discovered)
        # Prefer the venv bin (unresolved) so a symlinked interpreter doesn't move us out of the
        # venv; fall back to the resolved interpreter's sibling.
        for base in (Path(sys.executable), Path(sys.executable).resolve()):
            sibling = base.parent / "hb-assistant"
            if sibling.exists():
                return sibling
        return Path("hb-assistant")

    def _resolve_working_directory(self) -> Path:
        return self.pp.resolve_repo_root()

    def _program_arguments(self, executable: Path) -> list[str]:
        args: list[str] = [str(executable), "second-brain", "daily-run", "run"]
        args += ["--apply"] if self.apply_mode else ["--dry-run"]
        args += ["--max-persist-per-stage", str(self.max_persist_per_stage)]
        args += ["--max-total-persist", str(self.max_total_persist)]
        args += ["--limit", str(self.limit)]
        args += ["--lookahead-days", str(self.lookahead_days)]
        args += ["--timezone", self.timezone]
        args += ["--raw"] if self.raw else ["--no-raw"]
        args += ["--weekdays-only"] if self.weekdays_only else ["--all-days"]
        if self.write_obsidian:
            args += ["--write-obsidian"]
        if self.confirm_vault_write:
            args += ["--confirm-vault-write"]
        args += ["--generate-browser"] if self.generate_browser else ["--no-generate-browser"]
        args += ["--no-open-browser"]
        # Off by default → the installed schedule is byte-unchanged; only emitted when opted in.
        if self.include_relationship_candidates:
            args += ["--include-relationship-candidates"]
            # Scan-window overrides ride along only when explicitly set (else stage defaults apply).
            if self.relationship_scan_threads is not None:
                args += ["--relationship-scan-threads", str(self.relationship_scan_threads)]
            if self.relationship_scan_events is not None:
                args += ["--relationship-scan-events", str(self.relationship_scan_events)]
        if self.db_path:
            args += ["--db", self.db_path]
        args += ["--json"]
        return args

    def _calendar_intervals(self) -> list[dict[str, int]] | dict[str, int]:
        """Weekday-only → array of Mon–Fri entries; otherwise a single daily entry."""
        hour, minute = self._parse_time(self.time)
        if self.weekdays_only:
            return [{"Weekday": wd, "Hour": hour, "Minute": minute} for wd in range(1, 6)]
        return {"Hour": hour, "Minute": minute}

    def render_plist(self) -> dict[str, Any]:
        executable = self._resolve_executable_path()
        working_dir = self._resolve_working_directory()
        logs_dir = self.pp.get_logs_dir()
        out_log = logs_dir / "run-logs" / "launchd-daily-local-agent.out.log"
        err_log = logs_dir / "error-logs" / "launchd-daily-local-agent.err.log"
        return {
            "Label": self.label,
            "ProgramArguments": self._program_arguments(executable),
            "WorkingDirectory": str(working_dir),
            "StartCalendarInterval": self._calendar_intervals(),
            "StandardOutPath": str(out_log),
            "StandardErrorPath": str(err_log),
            "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        }

    # --- readiness + lifecycle -------------------------------------------------

    def ensure_log_dirs(self) -> None:
        logs = self.pp.get_logs_dir()
        (logs / "run-logs").mkdir(parents=True, exist_ok=True)
        (logs / "error-logs").mkdir(parents=True, exist_ok=True)

    def _readiness(self, plist: dict[str, Any]) -> dict[str, Any]:
        self.ensure_log_dirs()
        executable = Path(plist["ProgramArguments"][0])
        working_dir = Path(plist["WorkingDirectory"])
        args = plist["ProgramArguments"]
        grammar_ok = args[1:4] == ["second-brain", "daily-run", "run"]
        exe_ok = executable.exists() and executable.is_file() and os.access(executable, os.X_OK)
        wd_ok = working_dir.exists() and working_dir.is_dir()
        logs = self.pp.get_logs_dir()
        logs_ok = os.access(logs / "run-logs", os.W_OK) and os.access(logs / "error-logs", os.W_OK)
        blocking = not (exe_ok and wd_ok and grammar_ok and logs_ok)
        return {
            "executable_ready": exe_ok,
            "working_directory_ready": wd_ok,
            "command_grammar_valid": grammar_ok,
            "log_directories_writable": logs_ok,
            "blocking": blocking,
            "ready": not blocking,
        }

    def _redacted(self) -> str:
        return str(self.plist_path).replace(str(Path.home()), "~")

    def preview_install(self) -> dict[str, Any]:
        plist = self.render_plist()
        readiness = self._readiness(plist)
        return {
            "action": "preview_install",
            "label": self.label,
            "plist_path": self._redacted(),
            "plist": plist,
            "weekdays_only": self.weekdays_only,
            "catch_up_on_wake": "launchd StartCalendarInterval native (fires missed runs on wake)",
            "readiness": readiness,
            "commands": [
                f"launchctl load -w {self._redacted()}",
                f"launchctl kickstart -k gui/$(id -u)/{self.label}",
            ],
            "status": "blocking_diagnostic" if readiness["blocking"] else "ready",
            "note": "Dry-run only — no plist written. Real install uses launchctl on the plist.",
        }

    def install(self, dry_run: bool = True) -> dict[str, Any]:
        if dry_run:
            return self.preview_install()
        preview = self.preview_install()
        if preview["readiness"]["blocking"]:
            return {
                "action": "install",
                "label": self.label,
                "status": "blocked",
                "readiness": preview["readiness"],
                "message": "Install blocked: executable/working-directory/log readiness failed.",
            }
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        with self.plist_path.open("wb") as f:
            plistlib.dump(preview["plist"], f)
        try:
            subprocess.run(
                ["launchctl", "load", "-w", str(self.plist_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            status = "loaded"
        except subprocess.CalledProcessError as e:
            status = f"load_failed: {(e.stderr or str(e))[:200]}"
        return {
            "action": "install",
            "label": self.label,
            "plist_path": self._redacted(),
            "status": status,
            "weekdays_only": self.weekdays_only,
        }

    def uninstall(self, dry_run: bool = True) -> dict[str, Any]:
        if dry_run:
            return {
                "action": "preview_uninstall",
                "label": self.label,
                "plist_path": self._redacted(),
                "commands": [
                    f"launchctl unload -w {self._redacted()}",
                    f"rm -f {self._redacted()}",
                ],
            }
        if self.plist_path.exists():
            with suppress(Exception):
                subprocess.run(
                    ["launchctl", "unload", "-w", str(self.plist_path)],
                    check=False,
                    capture_output=True,
                )
            with suppress(Exception):
                self.plist_path.unlink()
            status = "uninstalled"
        else:
            status = "no_plist"
        return {"action": "uninstall", "label": self.label, "status": status}

    def status(self) -> dict[str, Any]:
        exists = self.plist_path.exists()
        plist = self.render_plist()
        return {
            "label": self.label,
            "plist_exists": exists,
            "plist_path": self._redacted() if exists else None,
            "schedule_time_local": self.time,
            "weekdays_only": self.weekdays_only,
            "catch_up_on_wake": True,
            "timezone": self.timezone,
            "program_arguments": plist["ProgramArguments"],
            "start_calendar_interval": plist["StartCalendarInterval"],
            "readiness": self._readiness(plist),
        }
