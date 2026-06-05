"""CLI for launchd automation (Phase 12).

`hb-assistant automation install-launchd --dry-run`
`hb-assistant automation kickstart`
etc.

Thin, safe, delegates to LaunchdManager. All output sanitized.
"""

from __future__ import annotations

import json

import typer

from hb_assistant.automation import LaunchdManager

app = typer.Typer(
    help="Launchd automation (install/uninstall/kickstart user LaunchAgent for morning run). Dry-run safe."
)


@app.command("install-launchd")
def install(
    dry_run: bool = typer.Option(
        True, "--dry-run", help="Preview plist + commands without writing or calling launchctl."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Install (or preview) the morning LaunchAgent."""
    mgr = LaunchdManager()
    result = mgr.install(dry_run=dry_run)
    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        typer.echo("automation install-launchd result:")
        typer.echo(json.dumps(result, indent=2, default=str))
    raise typer.Exit(0)


@app.command("uninstall-launchd")
def uninstall(
    dry_run: bool = typer.Option(True, "--dry-run"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    mgr = LaunchdManager()
    result = mgr.uninstall(dry_run=dry_run)
    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        typer.echo(json.dumps(result, indent=2, default=str))
    raise typer.Exit(0)


@app.command("kickstart")
def kickstart(json_out: bool = typer.Option(True, "--json")) -> None:
    """Force immediate kickstart of the agent (testing only)."""
    mgr = LaunchdManager()
    result = mgr.kickstart()
    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        typer.echo(json.dumps(result, indent=2, default=str))
    raise typer.Exit(0)
