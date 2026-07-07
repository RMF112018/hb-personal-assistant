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

from . import actions as actions_mod
from . import auth as auth_mod
from . import automation as auto_mod
from . import construction as construction_mod
from . import context_pack as context_pack_mod
from . import decision_memory as decision_memory_mod
from . import diagnostics as diag_mod
from . import email_calendar as email_calendar_mod
from . import files as files_mod
from . import graph as graph_mod
from . import intelligence as intelligence_mod
from . import launcher as launcher_mod
from . import mcp_nas as mcp_nas_mod
from . import memory as memory_mod
from . import procore as procore_mod
from . import qwen_worker as qwen_worker_mod
from . import research_packet as research_packet_mod
from . import review as review_mod
from . import run as run_mod
from . import scheduler as scheduler_mod
from . import search as search_mod
from . import second_brain as second_brain_mod

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
app.add_typer(actions_mod.app, name="actions")
app.add_typer(search_mod.app, name="search")
app.add_typer(run_mod.app, name="run")
app.add_typer(auto_mod.app, name="automation")
app.add_typer(construction_mod.app, name="construction-agent")
app.add_typer(procore_mod.app, name="procore")
app.add_typer(email_calendar_mod.app, name="email-calendar")
app.add_typer(graph_mod.app, name="graph")
app.add_typer(second_brain_mod.app, name="second-brain")
app.add_typer(mcp_nas_mod.mcp_app, name="mcp")
app.add_typer(launcher_mod.app, name="launcher")
app.add_typer(scheduler_mod.app, name="scheduler")
app.add_typer(qwen_worker_mod.app, name="qwen-worker")
app.add_typer(context_pack_mod.app, name="context-pack")
app.add_typer(memory_mod.app, name="memory")
app.add_typer(decision_memory_mod.app, name="decision-memory")
app.add_typer(review_mod.app, name="review")
app.add_typer(intelligence_mod.app, name="intelligence")
app.add_typer(research_packet_mod.app, name="research-packet")


# Explicit thin stubs for remaining command groups


def _make_stub(name: str):
    @app.command(name)
    def _stub(json_out: bool = typer.Option(False, "--json")) -> None:
        payload = {"implemented": False, "target_phase": "2-12", "command": name}
        typer.echo(json.dumps(payload, indent=2) if json_out else f"{name}: not implemented yet")
        raise typer.Exit(0)

    return _stub


for _n in ("vault", "sync", "brief"):
    _make_stub(_n)


cli = app

if __name__ == "__main__":  # pragma: no cover
    app()
