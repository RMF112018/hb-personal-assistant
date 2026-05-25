"""diagnostics subcommands.

Phase 1: Only `env --json` is fully functional and safe (no secrets ever emitted).
Other subcommands (auth, graph, scan-sensitive) are explicit stubs.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import typer

from hb_assistant.config.path_policy import PathPolicy

app = typer.Typer(help="Safe diagnostics and proof commands (read-only).")


def _safe_git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],  # repo root
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        return out
    except Exception:
        return None


@app.command("env")
def env_cmd(
    json_out: bool = typer.Option(True, "--json", help="Always emit machine-readable JSON (default)"),
) -> None:
    """Environment and path discovery (safe, no tokens/keys/bodies/PEMs)."""
    pp = PathPolicy()
    summary = pp.summary()

    data: Dict[str, Any] = {
        "phase": 1,
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "git": {
            "sha": _safe_git_sha(),
        },
        "paths": summary,
        "permissions": pp.check_perms(strict=False),
        "notes": "All values are safe for logging/evidence. No secret material is present.",
    }

    # Always pretty JSON for diagnostics (human + machine)
    typer.echo(json.dumps(data, indent=2, sort_keys=True))
    raise typer.Exit(0)


@app.command("auth")
def auth_stub(json_out: bool = typer.Option(False, "--json")) -> None:
    payload = {"implemented": False, "target_phase": 2, "note": "Token classification + cache status in Prompt 02"}
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("graph")
def graph_stub(
    safe: bool = typer.Option(True, "--safe"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    payload = {
        "implemented": False,
        "target_phase": 3,
        "safe_mode": safe,
        "note": "Graph connectivity + delegated proof in later phases (after Prompt 02/03)",
    }
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)


@app.command("scan-sensitive")
def scan_stub(
    repo: str = typer.Option(".", "--repo"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    payload = {
        "implemented": False,
        "target_phase": 11,
        "repo": repo,
        "note": "Sensitive artifact scanner (forbidden patterns in src + evidence) will be added in hardening phase",
    }
    typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(0)
