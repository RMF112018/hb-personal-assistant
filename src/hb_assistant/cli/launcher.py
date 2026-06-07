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


@app.command("dev")
def dev_cmd(
    plan: bool = typer.Option(
        False, "--plan", help="Plan only: resolve process specs without spawning."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Start HB Assistant Dev (current repo checkout, isolated dev DB, mock/local data)."""
    from hb_assistant.launcher.dev import build_dev_service

    _emit(build_dev_service().start(plan_only=plan), json_out=json_out)


@app.command("production")
def production_cmd(
    plan: bool = typer.Option(
        False, "--plan", help="Plan only: resolve process specs without spawning."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Start HB Assistant (current production build + production DB/config)."""
    from hb_assistant.launcher.production import build_production_service

    _emit(build_production_service().start(plan_only=plan), json_out=json_out)


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
