"""Root Typer CLI for hb-assistant.

Entry point: hb-assistant

Subcommand groups (per 11_CLI spec):
  auth, diagnostics, vault, sync, files, actions, brief, search, run, automation

Phase 1: Only diagnostics (env --json functional). All others are thin stubs.
"""

from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from hb_assistant import __version__

from . import diagnostics as diag_mod

app = typer.Typer(
    name="hb-assistant",
    help="HB Personal Assistant + Work Product Intelligence System (local-first MVP)",
    add_completion=True,
    rich_markup_mode="markdown",
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"hb-assistant {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """HB Personal Assistant CLI."""
    pass  # pragma: no cover


# Register diagnostics sub-app
app.add_typer(diag_mod.app, name="diagnostics")


# --- Stub command groups (Phase 1) ---

@app.command("auth")
def auth_cmd(
    status: bool = typer.Option(False, "--status", help="Show cached token status (stub)"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Auth commands (login/status/logout/clear-cache) — Phase 2 implementation."""
    payload = {
        "implemented": False,
        "target_phase": 2,
        "message": "Auth provider and token cache not yet implemented (Prompt 02).",
    }
    if json_out or status:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo("auth: not implemented (see --json or Phase 2)")
    raise typer.Exit(0 if json_out else 1)


@app.command("run")
def run_cmd(
    morning: bool = typer.Option(False, "--morning", help="Run morning workflow (dry-run supported in later phase)"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run commands (morning, etc.) — later phases."""
    payload = {
        "implemented": False,
        "target_phase": 8,
        "message": "Morning run orchestrator not yet implemented.",
        "dry_run_requested": dry_run,
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else "run: not implemented")
    raise typer.Exit(0)


# Explicit thin stubs for help discoverability (Phase 1)
def _make_stub(name: str):
    @app.command(name)
    def _stub(json_out: bool = typer.Option(False, "--json")) -> None:
        payload = {"implemented": False, "target_phase": "2-12", "command": name}
        typer.echo(json.dumps(payload, indent=2) if json_out else f"{name}: not implemented yet")
        raise typer.Exit(0)
    return _stub

for _n in ("vault", "sync", "files", "actions", "brief", "search", "automation"):
    _make_stub(_n)


if __name__ == "__main__":  # pragma: no cover
    app()
