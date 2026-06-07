"""`hb-assistant launcher` — Dev/Production launchers + close policy (pure-Python)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(help="HB Assistant launchers (Dev / Production) and window/session lifecycle.")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _start_or_open(
    service: Any,
    *,
    plan: bool,
    open_ui: bool,
    open_timeout_seconds: int | None,
    shell: str,
    frontend_url: str | None,
    force_restart: bool,
    json_out: bool,
) -> None:
    if shell not in ("browser", "pywebview"):
        _emit({"status": "invalid_shell", "requested": shell}, json_out=json_out, exit_code=2)
    if open_ui:
        result = service.open_session(
            shell=shell,
            open_timeout_seconds=open_timeout_seconds,
            frontend_url=frontend_url,
            plan_only=plan,
            force_restart=force_restart,
        )
    else:
        result = service.start(plan_only=plan, force_restart=force_restart)
    # Fail closed when a required port is held by an unknown process.
    exit_code = 2 if result.get("status") == "port_conflict" else 0
    _emit(result, json_out=json_out, exit_code=exit_code)


@app.command("dev")
def dev_cmd(
    plan: bool = typer.Option(
        False, "--plan", help="Plan only: resolve process specs without spawning."
    ),
    open_ui: bool = typer.Option(
        False, "--open/--no-open", help="Start the session and open the frontend UI."
    ),
    open_timeout_seconds: int = typer.Option(
        None, "--open-timeout-seconds", help="Frontend readiness wait (default: profile/config)."
    ),
    shell: str = typer.Option("browser", "--shell", help="browser | pywebview"),
    frontend_url: str = typer.Option(
        None, "--frontend-url", help="Override the resolved frontend URL."
    ),
    force_restart: bool = typer.Option(
        False,
        "--force-restart/--no-force-restart",
        help="Stop any prior session and free launcher-owned ports before starting.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Start HB Assistant Dev (current repo checkout, isolated dev DB, mock/local data)."""
    from hb_assistant.launcher.dev import build_dev_service

    _start_or_open(
        build_dev_service(),
        plan=plan,
        open_ui=open_ui,
        open_timeout_seconds=open_timeout_seconds,
        shell=shell,
        frontend_url=frontend_url,
        force_restart=force_restart,
        json_out=json_out,
    )


@app.command("production")
def production_cmd(
    plan: bool = typer.Option(
        False, "--plan", help="Plan only: resolve process specs without spawning."
    ),
    open_ui: bool = typer.Option(
        False, "--open/--no-open", help="Start the session and open the frontend UI."
    ),
    open_timeout_seconds: int = typer.Option(
        None, "--open-timeout-seconds", help="Frontend readiness wait (default: profile/config)."
    ),
    shell: str = typer.Option("browser", "--shell", help="browser | pywebview"),
    frontend_url: str = typer.Option(
        None, "--frontend-url", help="Override the resolved frontend URL."
    ),
    force_restart: bool = typer.Option(
        False,
        "--force-restart/--no-force-restart",
        help="Stop any prior session and free launcher-owned ports before starting.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Start HB Assistant (current production build + production DB/config)."""
    from hb_assistant.launcher.production import build_production_service

    _start_or_open(
        build_production_service(),
        plan=plan,
        open_ui=open_ui,
        open_timeout_seconds=open_timeout_seconds,
        shell=shell,
        frontend_url=frontend_url,
        force_restart=force_restart,
        json_out=json_out,
    )


@app.command("status")
def status_cmd(
    environment: str = typer.Option("production", "--environment", help="dev | production"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report launcher/process/scheduler status for an environment."""
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.launcher.service import LauncherService

    if environment not in ("dev", "production"):
        _emit(
            {"status": "invalid_environment", "requested": environment},
            json_out=json_out,
            exit_code=2,
        )
    _emit(LauncherService(resolve_profile(environment)).status(), json_out=json_out)  # type: ignore[arg-type]


@app.command("stop")
def stop_cmd(
    environment: str = typer.Option(..., "--environment", help="dev | production"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Stop ALL managed processes for an environment (including background services)."""
    from hb_assistant.launcher.profiles import resolve_profile
    from hb_assistant.launcher.service import LauncherService

    if environment not in ("dev", "production"):
        _emit(
            {"status": "invalid_environment", "requested": environment},
            json_out=json_out,
            exit_code=2,
        )
    _emit(LauncherService(resolve_profile(environment)).stop(), json_out=json_out)  # type: ignore[arg-type]


@app.command("close")
def close_cmd(
    environment: str = typer.Option(..., "--environment", help="dev | production"),
    action: str = typer.Option(..., "--action", help="quit | background"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Apply the window-close policy: quit (terminate all) or background (keep services)."""
    from hb_assistant.launcher.close_policy import ClosePolicy
    from hb_assistant.launcher.process_manager import ProcessManager
    from hb_assistant.launcher.profiles import resolve_profile

    if environment not in ("dev", "production"):
        _emit(
            {"status": "invalid_environment", "requested": environment},
            json_out=json_out,
            exit_code=2,
        )
    if action not in ("quit", "background"):
        _emit({"status": "invalid_action", "requested": action}, json_out=json_out, exit_code=2)
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    policy = ClosePolicy(profile, ProcessManager(profile))
    _emit(policy.apply(action), json_out=json_out)  # type: ignore[arg-type]


@app.command("cleanup")
def cleanup_cmd(
    environment: str = typer.Option(..., "--environment", help="dev | production"),
    apply: bool = typer.Option(
        False, "--apply", help="Terminate the stale launcher-owned processes (default: dry-run)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Identify (and with --apply terminate) stale launcher-owned processes for an env."""
    from hb_assistant.launcher.preflight import cleanup
    from hb_assistant.launcher.process_manager import ProcessManager
    from hb_assistant.launcher.profiles import resolve_profile

    if environment not in ("dev", "production"):
        _emit(
            {"status": "invalid_environment", "requested": environment},
            json_out=json_out,
            exit_code=2,
        )
    profile = resolve_profile(environment)  # type: ignore[arg-type]
    _emit(cleanup(profile, ProcessManager(profile), apply=apply), json_out=json_out)


@app.command("snapshot-dev-db")
def snapshot_dev_db_cmd(
    source: str = typer.Option(..., "--source", help="Source SQLite path to copy into the Dev DB."),
    confirm: bool = typer.Option(
        False, "--confirm", help="Required to overwrite an existing Dev DB."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Snapshot-copy a source SQLite into the isolated Dev DB (never mutates the source)."""
    from hb_assistant.launcher.profiles import resolve_profile, snapshot_source_db

    result = snapshot_source_db(resolve_profile("dev"), source_db=Path(source), confirm=confirm)
    exit_code = 0 if result.get("status") in ("ok", "confirmation_required") else 1
    _emit(result, json_out=json_out, exit_code=exit_code)
