"""Auth CLI subcommands (canonical grammar).

Canonical commands:
- hb-assistant auth login --json
- hb-assistant auth status --json
- hb-assistant auth logout --json
- hb-assistant auth clear-cache --json
"""

from __future__ import annotations

import json
from typing import Any, Dict

import typer

from hb_assistant.auth.providers import AppOnlyAuthProvider, DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy

app = typer.Typer(help="Authentication commands (delegated default; app-only proof/admin flow).")


def _build_providers() -> tuple[DelegatedAuthProvider, AppOnlyAuthProvider]:
    cfg = load_config()
    pp = PathPolicy(cfg)
    tenant = cfg.identity.tenant_id
    client = cfg.identity.client_id
    scopes = cfg.identity.delegated_scopes

    # Known cert path from prior evidence. Graceful if missing.
    cert_path = "/Users/bobbyfetting/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem"

    del_auth = DelegatedAuthProvider(tenant, client, scopes, path_policy=pp)
    app_auth = AppOnlyAuthProvider(tenant, client, cert_path, path_policy=pp)
    return del_auth, app_auth


def _emit(payload: Dict[str, Any], json_out: bool) -> None:
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))


@app.command("login")
def login_cmd(
    app_only: bool = typer.Option(False, "--app-only", help="Target app-only certificate flow (proof only)"),
    no_device_code: bool = typer.Option(False, "--no-device-code", help="Force interactive browser login instead of device code"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON (always safe, never contains tokens)"),
) -> None:
    """Perform login in delegated (default) or app-only mode."""
    del_auth, app_auth = _build_providers()
    target = app_auth if app_only else del_auth

    try:
        info = target.login(use_device_code=not no_device_code) if not app_only else target.login()
        payload = {"status": "login_success", "mode": "app_only" if app_only else "delegated", "info": info}
    except Exception as e:  # pragma: no cover
        payload = {"status": "login_failed", "mode": "app_only" if app_only else "delegated", "error": str(e)[:200]}

    _emit(payload, json_out)
    raise typer.Exit(0 if "success" in payload.get("status", "") else 1)


@app.command("status")
def status_cmd(
    app_only: bool = typer.Option(False, "--app-only", help="Show app-only token/cache status instead of delegated"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Show safe token/cache status."""
    try:
        del_auth, app_auth = _build_providers()
        target = app_auth if app_only else del_auth
        info = target.status_info()
        payload = {"mode": "app_only" if app_only else "delegated", **info}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0 if info.get("token_type") not in (None, "none") else 1)
    except typer.Exit:
        raise
    except Exception as e:  # pragma: no cover
        payload = {
            "mode": "app_only" if app_only else "delegated",
            "status": "status_error",
            "error": str(e)[:200],
        }
        _emit(payload, json_out)
        raise typer.Exit(1)


@app.command("logout")
def logout_cmd(
    app_only: bool = typer.Option(False, "--app-only", help="Logout app-only mode instead of delegated"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Logout and remove known account/cached auth for target mode."""
    try:
        del_auth, app_auth = _build_providers()
        target = app_auth if app_only else del_auth
        deleted = target.logout()
        payload = {"status": "logout_complete", "deleted_caches": deleted, "mode": "app_only" if app_only else "delegated"}
        _emit(payload, json_out)
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:  # pragma: no cover
        payload = {"status": "logout_error", "mode": "app_only" if app_only else "delegated", "error": str(e)[:200]}
        _emit(payload, json_out)
        raise typer.Exit(1)


@app.command("clear-cache")
def clear_cache_cmd(
    app_only: bool = typer.Option(False, "--app-only", help="Clear app-only cache instead of delegated"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Clear auth cache files for target mode."""
    try:
        del_auth, app_auth = _build_providers()
        target = app_auth if app_only else del_auth
        deleted = target.logout()  # existing provider behavior clears target cache
        payload = {"status": "clear_cache_complete", "deleted": deleted, "mode": "app_only" if app_only else "delegated"}
        _emit(payload, json_out)
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:  # pragma: no cover
        payload = {
            "status": "clear_cache_error",
            "mode": "app_only" if app_only else "delegated",
            "error": str(e)[:200],
        }
        _emit(payload, json_out)
        raise typer.Exit(1)
