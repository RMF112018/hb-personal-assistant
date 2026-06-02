"""Phase 08A daily-brief launchd scheduling — dry-run install preview (Prompt 13).

Builds a **preview only** launchd plist for scheduling
``hb-assistant second-brain daily-brief generate`` (default: 20:00 local, generating the
following day's brief, ``--mode apply``). No plist is written and ``launchctl`` is never
invoked — the only way to actually schedule is the operator running the documented
``launchctl load`` command (see ``docs/runbooks/phase-08a-second-brain-daily-brief-scheduling.md``).
Logs live outside the repo (Application Support); all paths are redacted (``$HOME`` -> ``~``).
Automation hardening (health checks, retries, weekend logic, alerting) is owned by the
Phase 08B Automation Health Agent. No raw content, no secrets, no external writeback.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from .models import LaunchdSchedulePreview
from .policy import load_daily_brief_policy_seed
from .store import write_launchd_schedule_preview

DEFAULT_SCHEDULE_LABEL = "com.hb.personal-assistant.second-brain-daily-brief"
_LOG_BASENAME = "launchd-second-brain-daily-brief"
_PHASE_08B_HANDOFF = (
    "Automation hardening (health checks, retries, weekend behavior, failure alerting, and "
    "real install/enable) is owned by the Phase 08B Automation Health Agent. This preview is "
    "dry-run only and performs no install."
)


def _redact(path: str | Path) -> str:
    """Redact the user home prefix (``$HOME`` -> ``~``)."""
    home = str(Path.home())
    text = str(path)
    return text.replace(home, "~") if text.startswith(home) else text


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hh, mm = value.split(":", 1)
        hour, minute = int(hh), int(mm)
    except (ValueError, AttributeError):
        return 20, 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return 20, 0
    return hour, minute


def _resolve_executable(repo_root: Path) -> str:
    """Best-effort hb-assistant entry point (venv bin preferred; never a secret)."""
    venv_bin = repo_root / ".venv" / "bin" / "hb-assistant"
    if venv_bin.exists():
        return str(venv_bin)
    found = shutil.which("hb-assistant")
    return found or str(venv_bin)


def build_daily_brief_schedule_preview(
    *,
    db_path: str | None = None,
    emit: bool = False,
) -> LaunchdSchedulePreview:
    """Build the dry-run launchd install preview for the scheduled daily brief.

    Reads the ``schedule`` section of the daily-brief policy seed. Never writes a plist or
    calls ``launchctl``. When ``emit`` is True, persists a metadata-only preview row to the
    V26 ``launchd_schedule_previews`` table (``mode='dry_run'``; guard column 0).
    """
    seed = load_daily_brief_policy_seed()
    schedule = seed.get("schedule", {}) if isinstance(seed.get("schedule"), dict) else {}
    label = str(schedule.get("label") or DEFAULT_SCHEDULE_LABEL)
    hour, minute = _parse_hhmm(str(schedule.get("time", "20:00")))
    day_offset = int(schedule.get("day_offset", 1))
    command_mode = str(schedule.get("command_mode", "apply"))

    pp = PathPolicy()
    repo_root = pp.resolve_repo_root()
    executable = _resolve_executable(repo_root)
    logs_dir = pp.get_logs_dir()
    out_log = logs_dir / "run-logs" / f"{_LOG_BASENAME}.out.log"
    err_log = logs_dir / "error-logs" / f"{_LOG_BASENAME}.err.log"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"

    program_arguments = [
        executable,
        "second-brain",
        "daily-brief",
        "generate",
        "--day-offset",
        str(day_offset),
        "--mode",
        command_mode,
        "--emit-receipt",
    ]
    program_arguments_redacted = [_redact(a) for a in program_arguments]

    plist: dict[str, Any] = {
        "Label": label,
        "ProgramArguments": program_arguments_redacted,
        "WorkingDirectory": _redact(repo_root),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": _redact(out_log),
        "StandardErrorPath": _redact(err_log),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }

    readiness = {
        "executable_resolved": bool(executable),
        "executable_exists": Path(executable).exists(),
        "working_directory_exists": repo_root.exists(),
        "logs_dir_outside_repo": str(repo_root) not in str(logs_dir),
        "command_args_present": len(program_arguments) >= 4,
        "blocking": False,  # a preview never blocks; real install is operator-run
    }

    plist_path_redacted = _redact(plist_path)
    manual_install_commands = [
        f"launchctl load -w {plist_path_redacted}",
        f"launchctl kickstart -k gui/$(id -u)/{label}",
        f"launchctl unload -w {plist_path_redacted}",
    ]

    preview = LaunchdSchedulePreview(
        label=label,
        hour=hour,
        minute=minute,
        day_offset=day_offset,
        command_mode=command_mode,
        program_arguments_redacted=program_arguments_redacted,
        plist=plist,
        plist_path_redacted=plist_path_redacted,
        log_out_redacted=_redact(out_log),
        log_err_redacted=_redact(err_log),
        log_dir_redacted=_redact(logs_dir),
        logs_outside_repo=str(repo_root) not in str(logs_dir),
        manual_install_commands=manual_install_commands,
        readiness=readiness,
        phase_08b_handoff=_PHASE_08B_HANDOFF,
        dry_run_install_only=True,
        external_writeback_performed=False,
    )

    if emit:
        preview.preview_id = write_launchd_schedule_preview(preview, db_path=db_path)
    return preview


def build_launchd_schedule_proof() -> dict[str, Any]:
    """Deterministic proof for ``launchd-schedule-proof.md`` (temp DB; preview only)."""
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/schedule.sqlite3"
        ConstructionStore(db)
        preview = build_daily_brief_schedule_preview(db_path=db, emit=True)

        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        row = dict(c.execute("SELECT * FROM launchd_schedule_previews").fetchone())
        c.close()

    blob = preview.model_dump_json()
    no_secrets = not any(
        t in blob
        for t in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret", "token")
    )
    home = str(Path.home())
    no_home_leak = home not in blob or home == "~"
    guard_zero = row["external_writeback_performed"] == 0
    program_args = preview.program_arguments_redacted

    proof_passed = bool(
        preview.preview_id
        and row["mode"] == "dry_run"
        and guard_zero
        and preview.dry_run_install_only is True
        and preview.external_writeback_performed is False
        and preview.logs_outside_repo is True
        and "generate" in program_args
        and "--mode" in program_args
        and "--day-offset" in program_args
        and preview.plist_path_redacted
        and row["plist_path_redacted"]
        and row["log_dir_redacted"]
        and no_secrets
        and no_home_leak
    )
    return {
        "proof": "phase_08a_launchd_schedule_dry_run",
        "proof_passed": proof_passed,
        "preview": {
            "label": preview.label,
            "schedule": {"hour": preview.hour, "minute": preview.minute},
            "day_offset": preview.day_offset,
            "command_mode": preview.command_mode,
            "program_arguments_redacted": program_args,
            "plist_path_redacted": preview.plist_path_redacted,
            "log_out_redacted": preview.log_out_redacted,
            "log_err_redacted": preview.log_err_redacted,
            "manual_install_commands": preview.manual_install_commands,
        },
        "persisted_row": {
            "mode": row["mode"],
            "label": row["label"],
            "plist_path_redacted": row["plist_path_redacted"],
            "log_dir_redacted": row["log_dir_redacted"],
            "external_writeback_performed": row["external_writeback_performed"],
        },
        "preview_persisted": bool(preview.preview_id),
        "mode_is_dry_run": row["mode"] == "dry_run",
        "guard_column_zero": guard_zero,
        "logs_outside_repo": preview.logs_outside_repo,
        "no_plist_written": True,  # this code path never writes a plist or calls launchctl
        "no_secrets_or_home_leak": no_secrets and no_home_leak,
        "guardrails": {
            "local_first": True,
            "dry_run_install_only": True,
            "no_launchctl_invocation": True,
            "no_plist_written": True,
            "logs_outside_repo": True,
            "no_external_writeback": True,
            "no_hidden_background_behavior": True,
            "phase_08b_owns_hardening": True,
        },
    }
