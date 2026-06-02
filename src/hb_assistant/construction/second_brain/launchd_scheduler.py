"""Phase 08B LaunchAgent scheduling + first-run-after-wake (Prompt 04).

A deterministic, read-only-by-default scheduling agent for the second-brain daily-brief
LaunchAgent (label ``com.hb.personal-assistant.second-brain-daily-brief``). It reports whether
the agent is installed and on-schedule (``evaluate_launchd_schedule``) and whether a catch-up
run is owed after the machine slept through the scheduled time
(``evaluate_first_run_after_wake``) — both with the Phase 08B structured reason codes.

The apply / uninstall surface is **real-but-policy-gated, fail-closed**: the plist-write /
``launchctl`` code path exists, but while the automation policy seed carries
``launchd.dry_run_install_only: true`` an ``--apply --confirm`` request returns a ``blocked``
result (``LAUNCHD_INSTALL_DISABLED_BY_POLICY``) and never writes a plist or invokes
``launchctl``. The real-write path is reachable only with an override policy
(``dry_run_install_only=False``) + ``confirm`` + an injected ``launchctl`` runner — exercised
only in tests against a temp LaunchAgents directory. No external writeback, no external
delivery, no raw content. Generated plists/logs live outside the repo
(``~/Library/LaunchAgents`` / Application Support).
"""

from __future__ import annotations

import plistlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed
from .daily_brief.scheduling import (
    _LOG_BASENAME,
    _resolve_executable,
    build_daily_brief_schedule_preview,
)

_FORBIDDEN_TOKENS = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
    "token",
)

# Structured reason codes (subset declared in the Phase 08B automation policy + gate contracts).
LAUNCHD_NOT_INSTALLED = "LAUNCHD_NOT_INSTALLED"
SCHEDULE_DRIFT = "SCHEDULE_DRIFT"
LAUNCHD_INSTALLED_OK = "LAUNCHD_INSTALLED_OK"
LAUNCHD_INSTALL_DISABLED_BY_POLICY = "LAUNCHD_INSTALL_DISABLED_BY_POLICY"
CATCH_UP_NEEDED = "CATCH_UP_NEEDED"
CATCH_UP_NOT_NEEDED = "CATCH_UP_NOT_NEEDED"
CATCH_UP_STALE = "CATCH_UP_STALE"

_DEFAULT_STALE_AFTER_DAYS = 3

LaunchctlRunner = Callable[[list[str]], int]


def _redact(path: str | Path) -> str:
    home = str(Path.home())
    text = str(path)
    return text.replace(home, "~") if text.startswith(home) else text


# --------------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------------
class LaunchdScheduleStatus(BaseModel):
    """Whether the daily-brief LaunchAgent is installed and on the policy schedule."""

    status: str  # "ok" | "not_installed" | "drift"
    reason_code: str
    label: str
    plist_installed: bool = False
    desired_schedule: dict[str, int] = {}
    installed_schedule: dict[str, int] | None = None
    plist_path_redacted: str = ""
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("launchd schedule detail must not carry raw/forbidden tokens")
        return value


class CatchUpStatus(BaseModel):
    """First-run-after-wake catch-up evaluation (metadata-only)."""

    status: str  # "not_needed" | "needed" | "stale"
    reason_code: str
    last_run_date: str | None = None
    stale_after_days: int = _DEFAULT_STALE_AFTER_DAYS
    schedule_time: str = ""
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("catch-up detail must not carry raw/forbidden tokens")
        return value


class LaunchdSchedulerStatus(BaseModel):
    """Combined scheduling-agent snapshot the status surface reports (no raw content)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    schedule: LaunchdScheduleStatus
    catch_up: CatchUpStatus
    policy_version: str = "unknown"
    schema_version: int = 0
    schema_expected: int = LATEST_SCHEMA_VERSION
    generated_utc: str = ""

    model_config = {"extra": "forbid"}


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def _resolved_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(PathPolicy().get_db_path())


def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive: scheduling must not crash
        return {}
    return seed if isinstance(seed, dict) else {}


def _policy_dry_run_only(seed: dict[str, Any] | None = None) -> bool:
    seed = seed if seed is not None else _safe_seed()
    launchd = seed.get("launchd", {}) if isinstance(seed.get("launchd"), dict) else {}
    return bool(launchd.get("dry_run_install_only", True))


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _schema_version(db_path: str | None) -> int:
    try:
        return SQLiteMigrator(_resolved_db(db_path)).current_version()
    except Exception:  # pragma: no cover - defensive
        return 0


def _latest_run_generated_utc(db_path: str | None) -> str | None:
    """Most recent ``daily_brief_runs.generated_utc`` (read-only; no migration)."""
    try:
        conn = get_connection(Path(db_path) if db_path is not None else None)
        if not _table_exists(conn, "daily_brief_runs"):
            return None
        row = conn.execute(
            "SELECT generated_utc FROM daily_brief_runs "
            "ORDER BY generated_utc DESC, brief_run_id DESC LIMIT 1"
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return row[0]


def _build_install_plist(
    *, label: str, hour: int, minute: int, day_offset: int, command_mode: str, log_dir: str | None
) -> dict[str, Any]:
    """Build the real (non-redacted) plist actually written on a permitted install."""
    pp = PathPolicy()
    repo_root = pp.resolve_repo_root()
    executable = _resolve_executable(repo_root)
    logs_dir = Path(log_dir) if log_dir else pp.get_logs_dir()
    out_log = logs_dir / "run-logs" / f"{_LOG_BASENAME}.out.log"
    err_log = logs_dir / "error-logs" / f"{_LOG_BASENAME}.err.log"
    return {
        "Label": label,
        "ProgramArguments": [
            executable,
            "second-brain",
            "daily-brief",
            "generate",
            "--day-offset",
            str(day_offset),
            "--mode",
            command_mode,
            "--emit-receipt",
        ],
        "WorkingDirectory": str(repo_root),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(out_log),
        "StandardErrorPath": str(err_log),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }


def _launch_agents_dir(launch_agents_dir: str | None) -> Path:
    if launch_agents_dir:
        return Path(launch_agents_dir)
    return Path.home() / "Library" / "LaunchAgents"


# --------------------------------------------------------------------------------------------
# Read-only evaluators
# --------------------------------------------------------------------------------------------
def evaluate_launchd_schedule(
    *, db_path: str | None = None, launch_agents_dir: str | None = None
) -> LaunchdScheduleStatus:
    """Read-only: is the daily-brief LaunchAgent installed and on the policy schedule?"""
    preview = build_daily_brief_schedule_preview(emit=False)
    label = preview.label
    desired = {"hour": preview.hour, "minute": preview.minute}
    plist_path = _launch_agents_dir(launch_agents_dir) / f"{label}.plist"
    redacted = _redact(plist_path)

    if not plist_path.exists():
        return LaunchdScheduleStatus(
            status="not_installed",
            reason_code=LAUNCHD_NOT_INSTALLED,
            label=label,
            plist_installed=False,
            desired_schedule=desired,
            plist_path_redacted=redacted,
            detail="plist_absent",
        )
    try:
        with plist_path.open("rb") as f:
            data = plistlib.load(f)
        sci = data.get("StartCalendarInterval", {}) or {}
        installed = {"hour": int(sci.get("Hour", -1)), "minute": int(sci.get("Minute", -1))}
    except Exception:
        return LaunchdScheduleStatus(
            status="drift",
            reason_code=SCHEDULE_DRIFT,
            label=label,
            plist_installed=True,
            desired_schedule=desired,
            plist_path_redacted=redacted,
            detail="plist_unreadable",
        )
    if installed == desired:
        return LaunchdScheduleStatus(
            status="ok",
            reason_code=LAUNCHD_INSTALLED_OK,
            label=label,
            plist_installed=True,
            desired_schedule=desired,
            installed_schedule=installed,
            plist_path_redacted=redacted,
            detail="schedule_matches",
        )
    return LaunchdScheduleStatus(
        status="drift",
        reason_code=SCHEDULE_DRIFT,
        label=label,
        plist_installed=True,
        desired_schedule=desired,
        installed_schedule=installed,
        plist_path_redacted=redacted,
        detail="installed_schedule_differs",
    )


def _parse_utc(value: str) -> datetime | None:
    try:
        text = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(text)
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_first_run_after_wake(
    *, db_path: str | None = None, now: datetime | None = None
) -> CatchUpStatus:
    """Read-only: is a catch-up run owed because the machine slept past the scheduled time?

    NEEDED  — no run yet today and the local time is past the scheduled time (machine likely
              asleep at the scheduled fire).
    STALE   — the last run is older than ``first_run_after_wake.stale_after_days``.
    NOT_NEEDED — a recent run already covers today, or it is not yet past the scheduled time.

    Fail-open to NEEDED on a parse failure (mirrors the orchestrator catch-up posture).
    """
    seed = _safe_seed()
    faw = (
        seed.get("first_run_after_wake", {})
        if isinstance(seed.get("first_run_after_wake"), dict)
        else {}
    )
    stale_after_days = int(faw.get("stale_after_days", _DEFAULT_STALE_AFTER_DAYS))

    preview = build_daily_brief_schedule_preview(emit=False)
    sched_hour, sched_minute = preview.hour, preview.minute
    schedule_time = f"{sched_hour:02d}:{sched_minute:02d}"

    now_local = now if now is not None else datetime.now()
    today = now_local.date()

    latest = _latest_run_generated_utc(db_path)
    if latest is None:
        return CatchUpStatus(
            status="needed",
            reason_code=CATCH_UP_NEEDED,
            last_run_date=None,
            stale_after_days=stale_after_days,
            schedule_time=schedule_time,
            detail="no_prior_run",
        )
    last_dt = _parse_utc(latest)
    if last_dt is None:
        return CatchUpStatus(
            status="needed",
            reason_code=CATCH_UP_NEEDED,
            last_run_date=None,
            stale_after_days=stale_after_days,
            schedule_time=schedule_time,
            detail="unparseable_last_run",
        )
    last_local_date = last_dt.astimezone().date()
    days = (today - last_local_date).days
    past_schedule = (now_local.hour, now_local.minute) >= (sched_hour, sched_minute)

    if days > stale_after_days:
        return CatchUpStatus(
            status="stale",
            reason_code=CATCH_UP_STALE,
            last_run_date=last_local_date.isoformat(),
            stale_after_days=stale_after_days,
            schedule_time=schedule_time,
            detail=f"last_run_{days}d_ago",
        )
    if days >= 1 and past_schedule:
        return CatchUpStatus(
            status="needed",
            reason_code=CATCH_UP_NEEDED,
            last_run_date=last_local_date.isoformat(),
            stale_after_days=stale_after_days,
            schedule_time=schedule_time,
            detail="no_run_today_past_schedule",
        )
    return CatchUpStatus(
        status="not_needed",
        reason_code=CATCH_UP_NOT_NEEDED,
        last_run_date=last_local_date.isoformat(),
        stale_after_days=stale_after_days,
        schedule_time=schedule_time,
        detail="recent_run_covers_today",
    )


# --------------------------------------------------------------------------------------------
# Apply / uninstall (real-but-policy-gated, fail-closed)
# --------------------------------------------------------------------------------------------
def preview_launchd_install(*, db_path: str | None = None) -> dict[str, Any]:
    """Dry-run preview of the LaunchAgent install (no plist write, no launchctl)."""
    preview = build_daily_brief_schedule_preview(emit=False)
    return {
        "command": "launchd-install",
        "status": "preview",
        "label": preview.label,
        "schedule": {"hour": preview.hour, "minute": preview.minute},
        "program_arguments_redacted": preview.program_arguments_redacted,
        "plist_path_redacted": preview.plist_path_redacted,
        "manual_install_commands": preview.manual_install_commands,
        "dry_run_install_only": True,
        "plist_written": False,
        "launchctl_invoked": False,
        "external_writeback_performed": 0,
    }


def _default_launchctl_runner(args: list[str]) -> int:  # pragma: no cover - real OS side effect
    import subprocess

    return subprocess.run(args, capture_output=True).returncode


def apply_launchd_install(
    *,
    confirm: bool = False,
    dry_run_install_only: bool | None = None,
    launch_agents_dir: str | None = None,
    log_dir: str | None = None,
    launchctl_runner: LaunchctlRunner | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Install (or refuse to install) the daily-brief LaunchAgent. Fail-closed by policy.

    Default posture (seed ``dry_run_install_only: true`` or missing ``confirm``) returns a
    ``blocked`` result with no plist write and no ``launchctl`` invocation. The real-write path
    is reachable only with ``dry_run_install_only=False`` **and** ``confirm`` — exercised only
    in tests via an injected temp ``launch_agents_dir`` + ``launchctl_runner``.
    """
    preview = build_daily_brief_schedule_preview(emit=False)
    label = preview.label
    if dry_run_install_only is None:
        dry_run_install_only = _policy_dry_run_only()

    if dry_run_install_only or not confirm:
        return {
            "command": "launchd-install",
            "label": label,
            "status": "blocked",
            "reason_code": LAUNCHD_INSTALL_DISABLED_BY_POLICY,
            "plist_written": False,
            "launchctl_invoked": False,
            "external_writeback_performed": 0,
            "detail": "dry_run_install_only" if dry_run_install_only else "confirm_required",
        }

    # Permitted real-write path (override policy + confirm).
    base = _launch_agents_dir(launch_agents_dir)
    base.mkdir(parents=True, exist_ok=True)
    plist_path = base / f"{label}.plist"
    plist = _build_install_plist(
        label=label,
        hour=preview.hour,
        minute=preview.minute,
        day_offset=preview.day_offset,
        command_mode=preview.command_mode,
        log_dir=log_dir,
    )
    with plist_path.open("wb") as f:
        plistlib.dump(plist, f)
    runner = launchctl_runner or _default_launchctl_runner
    rc = runner(["launchctl", "load", "-w", str(plist_path)])
    return {
        "command": "launchd-install",
        "label": label,
        "status": "installed",
        "reason_code": LAUNCHD_INSTALLED_OK,
        "plist_written": True,
        "launchctl_invoked": True,
        "launchctl_rc": rc,
        "external_writeback_performed": 0,
        "plist_path_redacted": _redact(plist_path),
    }


def uninstall_launchd(
    *,
    confirm: bool = False,
    dry_run_install_only: bool | None = None,
    launch_agents_dir: str | None = None,
    launchctl_runner: LaunchctlRunner | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Uninstall (or refuse to uninstall) the daily-brief LaunchAgent. Fail-closed by policy."""
    preview = build_daily_brief_schedule_preview(emit=False)
    label = preview.label
    if dry_run_install_only is None:
        dry_run_install_only = _policy_dry_run_only()

    if dry_run_install_only or not confirm:
        return {
            "command": "launchd-uninstall",
            "label": label,
            "status": "blocked",
            "reason_code": LAUNCHD_INSTALL_DISABLED_BY_POLICY,
            "plist_removed": False,
            "launchctl_invoked": False,
            "external_writeback_performed": 0,
            "detail": "dry_run_install_only" if dry_run_install_only else "confirm_required",
        }

    base = _launch_agents_dir(launch_agents_dir)
    plist_path = base / f"{label}.plist"
    runner = launchctl_runner or _default_launchctl_runner
    rc = runner(["launchctl", "unload", "-w", str(plist_path)])
    removed = False
    if plist_path.exists():
        plist_path.unlink()
        removed = True
    return {
        "command": "launchd-uninstall",
        "label": label,
        "status": "uninstalled",
        "reason_code": LAUNCHD_NOT_INSTALLED,
        "plist_removed": removed,
        "launchctl_invoked": True,
        "launchctl_rc": rc,
        "external_writeback_performed": 0,
    }


# --------------------------------------------------------------------------------------------
# Agent run + proof
# --------------------------------------------------------------------------------------------
def run_launchd_schedule_agent(
    *,
    db_path: str | None = None,
    launch_agents_dir: str | None = None,
    now: datetime | None = None,
    emit_receipt: bool = False,
) -> tuple[LaunchdSchedulerStatus, str | None]:
    """Evaluate schedule + catch-up (read-only); optionally emit a metadata-only V28 receipt.

    Returns ``(snapshot, agent_run_id|None)``. Receipt persistence is the only apply-capable
    path here and is off by default; the receipt carries status + reason code only.
    """
    generated = datetime.now(timezone.utc).isoformat()
    schedule = evaluate_launchd_schedule(db_path=db_path, launch_agents_dir=launch_agents_dir)
    catch_up = evaluate_first_run_after_wake(db_path=db_path, now=now)

    schedule_ok = schedule.status == "ok"
    catch_up_ok = catch_up.status == "not_needed"
    overall = "ok" if (schedule_ok and catch_up_ok) else "attention"
    if not schedule_ok:
        reason_code = schedule.reason_code
    elif not catch_up_ok:
        reason_code = catch_up.reason_code
    else:
        reason_code = LAUNCHD_INSTALLED_OK

    seed = _safe_seed()
    snapshot = LaunchdSchedulerStatus(
        overall_status=overall,
        reason_code=reason_code,
        schedule=schedule,
        catch_up=catch_up,
        policy_version=str(seed.get("version", "unknown")),
        schema_version=_schema_version(db_path),
        generated_utc=generated,
    )

    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="launchd_scheduler_agent",
            run_kind="launchd_schedule_eval",
            status=overall,
            reason_code=reason_code,
            started_utc=generated,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return snapshot, agent_run_id


def build_launchd_scheduler_proof() -> dict[str, Any]:
    """Deterministic proof for ``launchd-scheduling-proof.json`` (temp migrated DB)."""
    import json
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/launchd.sqlite3"
        ConstructionStore(db)  # migrate to LATEST
        la_dir = str(Path(tmp) / "LaunchAgents")  # empty -> not installed

        schedule = evaluate_launchd_schedule(db_path=db, launch_agents_dir=la_dir)
        catch_up = evaluate_first_run_after_wake(db_path=db)
        install_blocked = apply_launchd_install(confirm=True, launch_agents_dir=la_dir, db_path=db)
        uninstall_blocked = uninstall_launchd(confirm=True, launch_agents_dir=la_dir, db_path=db)

    blob = json.dumps(
        [
            schedule.model_dump(),
            catch_up.model_dump(),
            install_blocked,
            uninstall_blocked,
        ],
        default=str,
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    catch_up_codes = {CATCH_UP_NEEDED, CATCH_UP_NOT_NEEDED, CATCH_UP_STALE}
    proof_passed = bool(
        schedule.reason_code == LAUNCHD_NOT_INSTALLED
        and schedule.plist_installed is False
        and install_blocked["status"] == "blocked"
        and install_blocked["reason_code"] == LAUNCHD_INSTALL_DISABLED_BY_POLICY
        and install_blocked["plist_written"] is False
        and install_blocked["launchctl_invoked"] is False
        and install_blocked["external_writeback_performed"] == 0
        and uninstall_blocked["status"] == "blocked"
        and uninstall_blocked["launchctl_invoked"] is False
        and catch_up.reason_code in catch_up_codes
        and no_raw_content
    )
    return {
        "proof": "phase_08b_launchd_scheduling",
        "proof_passed": proof_passed,
        "schedule_reason_code": schedule.reason_code,
        "catch_up_reason_code": catch_up.reason_code,
        "install_blocked": install_blocked,
        "uninstall_blocked": uninstall_blocked,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "read_only_default": True,
            "dry_run_install_only": True,
            "no_launchctl_in_proof": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
