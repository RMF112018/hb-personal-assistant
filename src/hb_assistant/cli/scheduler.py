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
    from hb_assistant.scheduler.due import compute_next_run
    from hb_assistant.scheduler.state import SchedulerState

    _check_job(job, json_out)
    _check_env(environment, json_out)
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    state = SchedulerState.load(profile.scheduler_state_path, environment=environment)
    impl = get_backend(backend or default_backend_name(), profile)  # type: ignore[arg-type]
    now = datetime.now(timezone.utc)
    payload = {
        "command": "scheduler status",
        "environment": environment,
        "backend": impl.status(),
        "schedule_time_local": profile.scheduler.schedule_time,
        "timezone": profile.scheduler.timezone,
        "catch_up_on_wake": profile.scheduler.catch_up_on_wake,
        "next_expected_run": compute_next_run(
            now, profile.scheduler.schedule_time, profile.scheduler.timezone
        ).isoformat(),
        "last_status": state.last_status,
        "last_successful_schedule_date": state.last_successful_schedule_date,
        "last_attempted_schedule_date": state.last_attempted_schedule_date,
        "consecutive_failures": state.consecutive_failures,
        "last_receipt_path": state.last_receipt_path,
        "live_reads_enabled": profile.scheduler.enable_live_reads,
        "status": "ok",
    }
    _emit(payload, json_out=json_out)


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
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Execute the scheduled source-refresh (force, if-due, or foreground loop)."""
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.scheduler.runner import SchedulerRunner

    _check_job(job, json_out)
    _check_env(environment, json_out)
    if date_ is not None:
        try:
            date.fromisoformat(date_)
        except ValueError:
            _emit({"status": "invalid_date", "requested": date_}, json_out=json_out, exit_code=2)

    runner = SchedulerRunner(resolve_profile(environment))  # type: ignore[arg-type]

    if loop:  # pragma: no cover - long-running daemon
        while True:
            runner.tick(datetime.now(timezone.utc))
            time.sleep(max(5, interval))

    if if_due:
        result = runner.tick(datetime.now(timezone.utc))
        _emit({"command": "scheduler run", "environment": environment, **result}, json_out=json_out)

    target = date.fromisoformat(date_) if date_ else _today_target(runner)
    receipt = runner.run_once(schedule_date=target, trigger="manual")
    payload = receipt.model_dump()
    payload["command"] = "scheduler run"
    _emit(payload, json_out=json_out, exit_code=0 if receipt.status in ("ok", "degraded") else 1)


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
