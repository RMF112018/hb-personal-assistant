"""`hb-assistant scheduler` — repo-owned daily source-refresh scheduler."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

import typer

app = typer.Typer(help="Daily source-refresh scheduler (cross-platform; app-level catch-up).")

_JOB = "daily-source-refresh"


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _check_env(environment: str, json_out: bool) -> None:
    if environment not in ("dev", "production"):
        _emit(
            {"status": "invalid_environment", "requested": environment},
            json_out=json_out,
            exit_code=2,
        )


def _check_job(job: str, json_out: bool) -> None:
    if job != _JOB:
        _emit(
            {"status": "unknown_job", "requested": job, "expected": _JOB},
            json_out=json_out,
            exit_code=2,
        )


@app.command("install")
def install_cmd(
    job: str = typer.Argument(_JOB),
    time_: str = typer.Option("20:00", "--time", help="Local HH:MM (default 20:00)."),
    catch_up_on_wake: bool = typer.Option(True, "--catch-up-on-wake/--no-catch-up-on-wake"),
    environment: str = typer.Option(..., "--environment", help="dev | production"),
    mock_data: bool = typer.Option(False, "--mock-data", help="Dev: schedule mock/local refresh."),
    backend: Optional[str] = typer.Option(
        None, "--backend", help="launchd|windows|systemd|foreground"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Default dry-run writes no OS files."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Install the native scheduler artifact (dry-run by default)."""
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.scheduler.backends import default_backend_name, get_backend

    _check_job(job, json_out)
    _check_env(environment, json_out)
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    backend_name = backend or default_backend_name()
    impl = get_backend(backend_name, profile)  # type: ignore[arg-type]
    result = impl.install(dry_run=dry_run)
    _emit({"command": "scheduler install", "environment": environment, **result}, json_out=json_out)


@app.command("uninstall")
def uninstall_cmd(
    job: str = typer.Argument(_JOB),
    environment: str = typer.Option(..., "--environment"),
    backend: Optional[str] = typer.Option(None, "--backend"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.scheduler.backends import default_backend_name, get_backend

    _check_job(job, json_out)
    _check_env(environment, json_out)
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    impl = get_backend(backend or default_backend_name(), profile)  # type: ignore[arg-type]
    _emit(
        {
            "command": "scheduler uninstall",
            "environment": environment,
            **impl.uninstall(dry_run=dry_run),
        },
        json_out=json_out,
    )


@app.command("status")
def status_cmd(
    job: str = typer.Argument(_JOB),
    environment: str = typer.Option(..., "--environment"),
    backend: Optional[str] = typer.Option(None, "--backend"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.scheduler.backends import default_backend_name, get_backend
    from hb_assistant.scheduler.due import compute_next_run, current_local_date
    from hb_assistant.scheduler.state import SchedulerState

    _check_job(job, json_out)
    _check_env(environment, json_out)
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    state = SchedulerState.load(profile.scheduler_state_path, environment=environment)
    impl = get_backend(backend or default_backend_name(), profile)  # type: ignore[arg-type]
    now = datetime.now(timezone.utc)
    today = current_local_date(now, profile.scheduler.timezone)
    # Health flag: a last_successful_schedule_date in the future indicates corrupt state
    # (e.g. a prior future-dated manual run). Surface it rather than reporting as normal.
    future_success = bool(
        state.last_successful_schedule_date
        and state.last_successful_schedule_date > today.isoformat()
    )
    payload = {
        "command": "scheduler status",
        "environment": environment,
        "backend": impl.status(),
        "schedule_time_local": profile.scheduler.schedule_time,
        "timezone": profile.scheduler.timezone,
        "catch_up_on_wake": profile.scheduler.catch_up_on_wake,
        "current_local_date": today.isoformat(),
        "next_expected_run": compute_next_run(
            now, profile.scheduler.schedule_time, profile.scheduler.timezone
        ).isoformat(),
        "last_status": state.last_status,
        "last_successful_schedule_date": state.last_successful_schedule_date,
        "last_attempted_schedule_date": state.last_attempted_schedule_date,
        "consecutive_failures": state.consecutive_failures,
        "last_receipt_path": state.last_receipt_path,
        # Resolved environment paths + all three live-read gates (operator visibility).
        "db_path": _redact_home(str(profile.db_path)),
        "evidence_path": _redact_home(str(profile.evidence_path)),
        "live_reads_enabled": profile.scheduler.enable_live_reads,
        "enable_procore_live_reads": profile.scheduler.enable_procore_live_reads,
        "enable_graph_live_reads": profile.scheduler.enable_graph_live_reads,
        "last_run": _last_run_summary(state.last_receipt_path),
        "future_last_successful_schedule_date": future_success,
        "state_health": "future_success_date_detected" if future_success else "ok",
        "status": "ok",
    }
    _emit(payload, json_out=json_out)


def _redact_home(text: str) -> str:
    import os

    home = os.path.expanduser("~")
    return text.replace(home, "~") if text.startswith(home) else text


def _last_run_summary(receipt_path: Optional[str]) -> dict[str, object]:
    """Read the last scheduler receipt (safe fields only) so degradation is visible in status."""
    if not receipt_path:
        return {"available": False}
    try:
        import json as _json
        from pathlib import Path

        data = _json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    except Exception:
        return {"available": False}
    return {
        "available": True,
        "status": data.get("status"),
        "orchestrator_status": data.get("orchestrator_status"),
        "failure_count": data.get("failure_count", 0),
        "next_operator_action": data.get("next_operator_action"),
        "schedule_date": data.get("schedule_date"),
        "evidence_summary_path": data.get("evidence_summary_path"),
    }


@app.command("due")
def due_cmd(
    job: str = typer.Argument(_JOB),
    environment: str = typer.Option(..., "--environment"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report whether a run is currently due (and the catch-up reason)."""
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.scheduler.due import decide_catch_up
    from hb_assistant.scheduler.state import SchedulerState

    _check_job(job, json_out)
    _check_env(environment, json_out)
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    state = SchedulerState.load(profile.scheduler_state_path, environment=environment)
    now = datetime.now(timezone.utc)
    d = decide_catch_up(
        now,
        state,
        schedule_time_local=profile.scheduler.schedule_time,
        timezone=profile.scheduler.timezone,
        catch_up_on_wake=profile.scheduler.catch_up_on_wake,
    )
    _emit(
        {
            "command": "scheduler due",
            "environment": environment,
            "should_run": d.should_run,
            "schedule_date": d.schedule_date,
            "reason": d.reason,
            "next_expected_run": d.next_expected_run,
            "now_local": d.now_local,
            "status": "ok",
        },
        json_out=json_out,
    )


@app.command("run")
def run_cmd(
    job: str = typer.Argument(_JOB),
    environment: str = typer.Option(..., "--environment"),
    date_: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD; default today's target."),
    if_due: bool = typer.Option(
        False, "--if-due", help="Run only if due (native backends use this)."
    ),
    loop: bool = typer.Option(False, "--loop", help="Run the foreground tick loop."),
    interval: int = typer.Option(300, "--interval", help="Loop tick interval seconds."),
    mock_data: bool = typer.Option(
        False, "--mock-data", help="Dev mock (profile already governs)."
    ),
    allow_future_date: bool = typer.Option(
        False,
        "--allow-future-date",
        help="Fixtures/proofs only: permit a --date later than today (override; may "
        "advance catch-up state to a future date).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Execute the scheduled source-refresh (force, if-due, or foreground loop)."""
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.scheduler.due import current_local_date
    from hb_assistant.scheduler.runner import SchedulerRunner

    _check_job(job, json_out)
    _check_env(environment, json_out)
    if date_ is not None:
        try:
            date.fromisoformat(date_)
        except ValueError:
            _emit({"status": "invalid_date", "requested": date_}, json_out=json_out, exit_code=2)

    profile = resolve_profile(environment)  # type: ignore[arg-type]

    # Fail-closed guard: a manual run may not target a schedule date later than the
    # current local date — that corrupts catch-up state. Reject BEFORE any execution,
    # state mutation, or receipt write. --allow-future-date is an explicit override.
    if date_ is not None and not allow_future_date:
        today = current_local_date(datetime.now(timezone.utc), profile.scheduler.timezone)
        if date.fromisoformat(date_) > today:
            _emit(
                {
                    "command": "scheduler run",
                    "environment": environment,
                    "status": "not_ready",
                    "error": "future_schedule_date_not_allowed",
                    "requested_date": date_,
                    "current_local_date": today.isoformat(),
                    "guardrail": (
                        "manual scheduler runs may not target a schedule date later than "
                        "the current local date; this protects catch-up state. Use "
                        "--allow-future-date for fixtures/proofs only."
                    ),
                    "ran": False,
                },
                json_out=json_out,
                exit_code=2,
            )

    runner = SchedulerRunner(profile)

    if loop:  # pragma: no cover - long-running daemon
        while True:
            runner.tick(datetime.now(timezone.utc))
            time.sleep(max(5, interval))

    if if_due:
        result = runner.tick(datetime.now(timezone.utc))
        _emit({"command": "scheduler run", "environment": environment, **result}, json_out=json_out)

    target = date.fromisoformat(date_) if date_ else _today_target(runner)
    trigger = "manual_future_override" if (date_ and allow_future_date) else "manual"
    receipt = runner.run_once(schedule_date=target, trigger=trigger)
    payload = receipt.model_dump()
    payload["command"] = "scheduler run"
    # Manual runs surface degradation to the operator/CI via a nonzero exit (2 = degraded,
    # 1 = failed); a clean run exits 0. Unattended scheduler ticks keep exit 0 for degraded
    # (see runner.tick) so launchd success detection is unchanged.
    if receipt.status == "failed":
        exit_code = 1
    elif receipt.status == "degraded":
        exit_code = 2
    else:
        exit_code = 0
    _emit(payload, json_out=json_out, exit_code=exit_code)


@app.command("reset")
def reset_cmd(
    job: str = typer.Argument(_JOB),
    environment: str = typer.Option(..., "--environment"),
    confirm: bool = typer.Option(False, "--confirm", help="Required to clear scheduler state."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Reset scheduler state for an environment (recovers corrupt/future state)."""
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.scheduler.state import SchedulerState

    _check_job(job, json_out)
    _check_env(environment, json_out)
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    if not confirm:
        _emit(
            {
                "command": "scheduler reset",
                "environment": environment,
                "status": "confirmation_required",
                "hint": "re-run with --confirm to clear scheduler state",
                "state_path": str(profile.scheduler_state_path),
            },
            json_out=json_out,
        )
    fresh = SchedulerState(
        environment=environment,
        schedule_time_local=profile.scheduler.schedule_time,
        timezone=profile.scheduler.timezone,
        catch_up_on_wake=profile.scheduler.catch_up_on_wake,
    )
    fresh.save(profile.scheduler_state_path)
    _emit(
        {
            "command": "scheduler reset",
            "environment": environment,
            "status": "ok",
            "reset": True,
            "state": fresh.model_dump(),
        },
        json_out=json_out,
    )


def _today_target(runner: Any) -> date:
    from hb_assistant.scheduler.due import decide_catch_up

    sc = runner.profile.scheduler
    state = runner._load_state()
    d = decide_catch_up(
        datetime.now(timezone.utc),
        state,
        schedule_time_local=sc.schedule_time,
        timezone=sc.timezone,
        catch_up_on_wake=True,
    )
    return date.fromisoformat(d.schedule_date)
