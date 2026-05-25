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
from hb_assistant.auth.providers import AppOnlyAuthProvider, DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy

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
    login: bool = typer.Option(False, "--login", help="Perform delegated (or --app-only) login"),
    status: bool = typer.Option(False, "--status", help="Show safe token/cache status"),
    logout: bool = typer.Option(False, "--logout", help="Logout and remove accounts (delegated by default)"),
    clear_cache: bool = typer.Option(False, "--clear-cache", help="Delete cache files (delegated by default)"),
    app_only: bool = typer.Option(False, "--app-only", help="Target app-only certificate flow (proof only)"),
    no_device_code: bool = typer.Option(False, "--no-device-code", help="Force interactive browser login instead of device code"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON (always safe, never contains tokens)"),
) -> None:
    """Auth commands (login/status/logout/clear-cache) — real Phase 2 implementation.

    All --json output is sanitized. Never prints or logs access/refresh/id tokens.
    """
    cfg = load_config()
    pp = PathPolicy(cfg)
    tenant = cfg.identity.tenant_id
    client = cfg.identity.client_id
    scopes = cfg.identity.delegated_scopes

    # Known cert path from Phase 0 evidence (graceful if missing)
    cert_path = "/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem"

    del_auth = DelegatedAuthProvider(tenant, client, scopes, path_policy=pp)
    app_auth = AppOnlyAuthProvider(tenant, client, cert_path, path_policy=pp)

    target = app_auth if app_only else del_auth

    if login:
        try:
            info = target.login(use_device_code=not no_device_code) if not app_only else target.login()
            payload = {"status": "login_success", "mode": "app_only" if app_only else "delegated", "info": info}
        except Exception as e:
            payload = {"status": "login_failed", "mode": "app_only" if app_only else "delegated", "error": str(e)[:200]}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0 if "success" in payload.get("status", "") else 1)

    if logout:
        deleted = target.logout()
        payload = {"status": "logout_complete", "deleted_caches": deleted, "mode": "app_only" if app_only else "delegated"}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    if clear_cache:
        deleted = target.logout()  # logout does clear for the target
        payload = {"status": "clear_cache_complete", "deleted": deleted}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    # Default or explicit --status
    info = target.status_info()
    payload = {"mode": "app_only" if app_only else "delegated", **info}
    typer.echo(json.dumps(payload, indent=2))
    # Non-zero only if no token at all (for scripting)
    raise typer.Exit(0 if info.get("token_type") not in (None, "none") else 1)


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
