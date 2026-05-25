"""Root Typer CLI for hb-assistant.

Entry point: hb-assistant

Subcommand groups (per 11_CLI spec):
  auth, diagnostics, vault, sync, files, actions, brief, search, run, automation

Canonical remediation grammar:
- auth and run are true subcommand groups (not option-flag root commands).
"""

from __future__ import annotations

import json

import typer

from hb_assistant import __version__

from . import auth as auth_mod
from . import automation as auto_mod
from . import diagnostics as diag_mod
from . import files as files_mod
from . import run as run_mod
from . import search as search_mod

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


app.add_typer(auth_mod.app, name="auth")
app.add_typer(diag_mod.app, name="diagnostics")
app.add_typer(files_mod.app, name="files")
app.add_typer(search_mod.app, name="search")
app.add_typer(run_mod.app, name="run")
app.add_typer(auto_mod.app, name="automation")


# Explicit thin stubs for remaining command groups

def _make_stub(name: str):
    @app.command(name)
    def _stub(json_out: bool = typer.Option(False, "--json")) -> None:
        payload = {"implemented": False, "target_phase": "2-12", "command": name}
        typer.echo(json.dumps(payload, indent=2) if json_out else f"{name}: not implemented yet")
        raise typer.Exit(0)

    return _stub


for _n in ("vault", "sync", "actions", "brief"):
    _make_stub(_n)


cli = app

if __name__ == "__main__":  # pragma: no cover
    app()
