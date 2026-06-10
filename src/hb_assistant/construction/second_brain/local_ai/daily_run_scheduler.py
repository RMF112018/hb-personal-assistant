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

from .vault_brief_policy import governed_brief_dir

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
        synthesize: bool = True,
        model_enriched_intelligence: bool = True,
        email_raw_enrichment: bool = True,
        email_raw_enrichment_max_persist: Optional[int] = None,
        timezone: str = "America/New_York",
        db_path: Optional[str] = None,
        vault_brief_dir: Optional[str] = None,
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
        self.synthesize = synthesize
        self.model_enriched_intelligence = model_enriched_intelligence
        self.email_raw_enrichment = email_raw_enrichment
        self.email_raw_enrichment_max_persist = email_raw_enrichment_max_persist
        self.timezone = timezone
        self.db_path = db_path
        self.vault_brief_dir = vault_brief_dir
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

    def _resolve_vault_brief_dir(self) -> Path:
        """Effective governed brief folder pinned into the schedule (policy-backed by default)."""
        if self.vault_brief_dir:
            return Path(self.vault_brief_dir)
        return governed_brief_dir(path_policy=self.pp)

    def _redacted_vault_brief_dir(self) -> str:
        target = self._resolve_vault_brief_dir()
        try:
            return "~/" + str(target.resolve().relative_to(Path.home()))
        except ValueError:
            return f"{target.parent.name}/{target.name}"

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
            # Pin the governed brief folder explicitly so the installed schedule can never drift back
            # to the legacy Phase 08A folder (the routing failure this correction fixes).
            args += ["--vault-brief-dir", str(self._resolve_vault_brief_dir())]
        if self.confirm_vault_write:
            args += ["--confirm-vault-write"]
        args += ["--generate-browser"] if self.generate_browser else ["--no-generate-browser"]
        args += ["--synthesize"] if self.synthesize else ["--no-synthesize"]
        # Default-on Model Enriched Intelligence + V45 email raw enrichment, emitted explicitly so the
        # installed schedule's effective posture is unambiguous in the plist (never auto-open browser).
        args += (
            ["--model-enriched-intelligence"]
            if self.model_enriched_intelligence
            else ["--no-model-enriched-intelligence"]
        )
        args += (
            ["--email-raw-enrichment"]
            if self.email_raw_enrichment
            else ["--no-email-raw-enrichment"]
        )
        if self.email_raw_enrichment and self.email_raw_enrichment_max_persist is not None:
            args += [
                "--email-raw-enrichment-max-persist",
                str(self.email_raw_enrichment_max_persist),
            ]
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
        blocking_diagnostics: list[str] = []
        if not exe_ok:
            blocking_diagnostics.append("executable_not_found_or_not_executable")
        if not wd_ok:
            blocking_diagnostics.append("working_directory_missing")
        if not grammar_ok:
            blocking_diagnostics.append("command_grammar_invalid")
        if not logs_ok:
            blocking_diagnostics.append("log_directories_not_writable")
        return {
            "executable_ready": exe_ok,
            "executable_path_redacted": self._redact_path(executable),
            "working_directory_ready": wd_ok,
            "working_directory_redacted": self._redact_path(working_dir),
            "command_grammar_valid": grammar_ok,
            "log_directories_writable": logs_ok,
            "log_run_dir_redacted": self._redact_path(logs / "run-logs"),
            "log_error_dir_redacted": self._redact_path(logs / "error-logs"),
            "plist_exists": self.plist_path.exists(),
            "blocking": blocking,
            "blocking_diagnostics": blocking_diagnostics,
            "ready": not blocking,
        }

    def _redacted(self) -> str:
        return str(self.plist_path).replace(str(Path.home()), "~")

    @staticmethod
    def _redact_path(p: Path) -> str:
        try:
            return "~/" + str(p.resolve().relative_to(Path.home()))
        except ValueError:
            return f"{p.parent.name}/{p.name}"

    def _effective_config(self) -> dict[str, Any]:
        """Effective scheduled-run posture surfaced to the operator (never a secret)."""
        return {
            "model_enriched_intelligence": self.model_enriched_intelligence,
            "email_raw_enrichment": self.email_raw_enrichment,
            "email_raw_enrichment_max_persist": self.email_raw_enrichment_max_persist,
            "browser_generation": self.generate_browser,
            "browser_auto_open": False,
            "synthesize_narrative": self.synthesize,
            "raw_local_consumption": self.raw,
            "write_obsidian": self.write_obsidian,
            "apply_mode": self.apply_mode,
            "max_persist_per_stage": self.max_persist_per_stage,
            "max_total_persist": self.max_total_persist,
            "db_path_redacted": self._redact_path(Path(self.db_path)) if self.db_path else None,
        }

    def _last_run_state(self) -> dict[str, Any]:
        """Read the redacted daily-run status pointers (latest result + last successful brief)."""
        import json

        status_dir = self.pp.get_app_support() / "daily-run-status"
        out: dict[str, Any] = {
            "latest_status_path_redacted": None,
            "last_run_result": None,
            "last_successful_brief_path": None,
            "last_successful_brief_date": None,
        }
        latest = status_dir / "latest-status.json"
        if latest.exists():
            out["latest_status_path_redacted"] = self._redact_path(latest)
            try:
                data = json.loads(latest.read_text(encoding="utf-8"))
                rs = data.get("run_summary") or {}
                out["last_run_result"] = rs.get("result") or data.get("status")
            except Exception:
                pass
        last_good = status_dir / "last-successful.json"
        if last_good.exists():
            try:
                data = json.loads(last_good.read_text(encoding="utf-8"))
                out["last_successful_brief_path"] = data.get("browser_latest_path")
                out["last_successful_brief_date"] = data.get("brief_date")
            except Exception:
                pass
        return out

    def preview_install(self) -> dict[str, Any]:
        plist = self.render_plist()
        readiness = self._readiness(plist)
        return {
            "action": "preview_install",
            "label": self.label,
            "plist_path": self._redacted(),
            "plist": plist,
            "weekdays_only": self.weekdays_only,
            "schedule_time_local": self.time,
            "timezone": self.timezone,
            "vault_brief_dir_redacted": self._redacted_vault_brief_dir(),
            "catch_up_on_wake": "launchd StartCalendarInterval native (fires missed runs on wake)",
            "effective_config": self._effective_config(),
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
            "weekday_intervals": plist["StartCalendarInterval"],
            "vault_brief_dir_redacted": self._redacted_vault_brief_dir(),
            "catch_up_on_wake": True,
            "catch_up_on_wake_explanation": (
                "launchd fires a missed weekday interval on the next wake; the wrapper's date policy "
                "resolves a weekend wake of a missed Friday to the Friday brief and skips weekends."
            ),
            "timezone": self.timezone,
            "effective_config": self._effective_config(),
            "program_arguments": plist["ProgramArguments"],
            "start_calendar_interval": plist["StartCalendarInterval"],
            "readiness": self._readiness(plist),
            "last_run": self._last_run_state(),
        }
