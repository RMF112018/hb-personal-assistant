"""Procore CLI subcommands (Phase 01 Step 10 / Prompt 09).

Read-only, dry-run dashboard. No live Procore API call is wired in this
prompt — auth status is a documented stub, the endpoint audit is pure
projection over the seeded contract + projects registry.

Commands:
- ``hb-assistant procore auth status [--json]``
- ``hb-assistant procore tools list [--json]``
- ``hb-assistant procore tools audit --project KEY [--json]``
- ``hb-assistant procore mapping validate [--json]``
- ``hb-assistant procore mapping list [--json]``
- ``hb-assistant procore projects list [--json]``
- ``hb-assistant procore companies list [--json]``
"""

from __future__ import annotations

import hashlib
import json
import sys
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import typer
from pydantic import ValidationError

from hb_assistant.procore import (
    EndpointAuditor,
    EndpointContractError,
    LiveEnvNotSet,
    ProcoreProjectsError,
    assert_live_mapping_strict,
    check_auth_status,
    load_endpoint_contract,
    load_procore_projects,
    require_live_env,
)
from hb_assistant.procore.errors import ProcoreAPIError, ProcoreRateLimitError
from hb_assistant.procore.models import EndpointAuditRunReceipt
from hb_assistant.procore.pagination import RetryPolicy

app = typer.Typer(help="Procore foundation: read-only endpoint audit (dry-run only).")
auth_app = typer.Typer(help="Procore auth status (no live call).")
tools_app = typer.Typer(help="Procore endpoint catalog + dry-run audit.")
mapping_app = typer.Typer(help="Procore project mapping validation.")
projects_app = typer.Typer(help="Procore projects registry (read-only).")
companies_app = typer.Typer(help="Procore company context (read-only).")
audit_app = typer.Typer(help="Procore endpoint audit (dry-run default; live opt-in manual only).")
obsidian_app = typer.Typer(help="Procore Obsidian deterministic output (Prompt 10). Dry-run default. --apply explicit gate only. Hybrid procore-*.md in 01_Projects/. No secrets/LLM.")
app.add_typer(auth_app, name="auth")
app.add_typer(tools_app, name="tools")
app.add_typer(mapping_app, name="mapping")
app.add_typer(projects_app, name="projects")
app.add_typer(companies_app, name="companies")
app.add_typer(audit_app, name="audit")
app.add_typer(obsidian_app, name="obsidian", help="Procore Obsidian preview (Prompt 10) — deterministic; see procore obsidian preview --help")


_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": True,
    "live_calls_disabled": True,
    "correspondence_excluded": True,
    "schedule_tasks_deferred": True,
}


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


@auth_app.command("status")
def auth_status(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report Procore auth-credential presence (no live call).

    Phase 04 Prompt 02 extends the envelope with the local OAuth cache state
    (presence flags + ``expires_in_seconds_if_known``) and the default
    token-provider chain order. No token values are ever emitted.
    """
    from datetime import datetime, timezone

    from hb_assistant.procore.token_provider import (
        default_procore_token_provider,
        read_token_cache_payload,
    )

    report = check_auth_status()
    cache_payload = read_token_cache_payload()
    cache_present = cache_payload is not None
    access_present = bool(
        cache_payload and isinstance(cache_payload.get("access_token"), str) and cache_payload["access_token"]
    )
    refresh_present = bool(
        cache_payload and isinstance(cache_payload.get("refresh_token"), str) and cache_payload["refresh_token"]
    )
    expires_in_seconds: int | None = None
    if cache_payload and isinstance(cache_payload.get("expires_at"), str):
        try:
            deadline = datetime.fromisoformat(
                cache_payload["expires_at"].replace("Z", "+00:00")
            )
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            expires_in_seconds = int((deadline - datetime.now(timezone.utc)).total_seconds())
        except ValueError:
            expires_in_seconds = None

    chain = default_procore_token_provider()
    chain_order = [getattr(p, "kind", type(p).__name__) for p in getattr(chain, "providers", ())]

    payload = {
        "command": "hb-assistant procore auth status",
        "report": report.model_dump(),
        "cache_present": cache_present,
        "access_token_present": access_present,
        "refresh_token_present": refresh_present,
        "expires_in_seconds_if_known": expires_in_seconds,
        "chain_order": chain_order,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


def _build_oauth_client() -> Any:
    from hb_assistant.procore.config import load_procore_app_profile
    from hb_assistant.procore.oauth import ProcoreOAuthClient

    profile = load_procore_app_profile()
    return ProcoreOAuthClient(environment=profile.environment)


def _redacted_oauth_envelope(
    command: str,
    *,
    kind: str,
    token_set: Any,
) -> dict[str, Any]:
    expires_in = None
    try:
        expires_in = int(token_set.expires_in_seconds())
    except Exception:  # noqa: BLE001 — diagnostic only
        expires_in = None
    return {
        "command": command,
        "ok": True,
        "kind": kind,
        "access_token_cached": True,
        "refresh_token_cached": bool(getattr(token_set, "refresh_token", None)),
        "expires_in_seconds": expires_in,
        "guardrails": _GUARDRAILS,
    }


@auth_app.command("login")
def auth_login(
    code: Optional[str] = typer.Option(
        None,
        "--code",
        help="Authorization code from the OOB redirect (paste the value Procore displays after consent).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """First-time OAuth login via Procore's OOB Installed-Apps flow.

    Prints the authorization URL when ``--code`` is not supplied; the operator
    opens the URL, signs in, and pastes the returned code. The exchange is
    performed against ``<oauth_base>/oauth/token`` and the resulting access +
    refresh tokens are written to the local cache file with ``0o600`` perms.
    No token values are echoed.
    """
    from hb_assistant.procore.config import SecretNotAvailableError
    from hb_assistant.procore.oauth import ProcoreOAuthError
    from hb_assistant.procore.token_provider import write_token_cache

    client = _build_oauth_client()
    if code is None:
        url = client.build_authorization_url()
        typer.echo(
            "Open the following URL in a browser, sign in, then paste the "
            "displayed authorization code:\n  "
            f"{url}"
        )
        code = typer.prompt("Authorization code", hide_input=False)
    try:
        token_set = client.exchange_authorization_code(code)
        cache_path = write_token_cache(token_set)
    except SecretNotAvailableError:
        _emit(
            {
                "command": "hb-assistant procore auth login",
                "ok": False,
                "kind": "secret_not_configured",
                "reason": "no_client_secret_in_keychain_env_or_protected_file",
                "hint": (
                    "Install the Procore client secret with: "
                    "security add-generic-password -U "
                    "-s 'hb-assistant-procore' -a 'client-secret' -w '<value>'"
                ),
                "guardrails": _GUARDRAILS,
            },
            json_out=json_out,
            exit_code=1,
        )
        return
    except ProcoreOAuthError as exc:
        _emit(
            {
                "command": "hb-assistant procore auth login",
                "ok": False,
                "kind": "oauth_login_failed",
                "status": int(exc.status),
                "correlation_id": exc.correlation_id,
                "guardrails": _GUARDRAILS,
            },
            json_out=json_out,
            exit_code=1,
        )
        return
    payload = _redacted_oauth_envelope(
        "hb-assistant procore auth login",
        kind="oauth_login",
        token_set=token_set,
    )
    payload["cache_path"] = str(cache_path)
    _emit(payload, json_out=json_out)


@auth_app.command("refresh")
def auth_refresh(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Force-refresh the locally cached OAuth tokens using the stored refresh token."""
    from hb_assistant.procore.config import SecretNotAvailableError
    from hb_assistant.procore.oauth import ProcoreOAuthError
    from hb_assistant.procore.token_provider import (
        read_token_cache_payload,
        write_token_cache,
    )

    payload = read_token_cache_payload()
    if not payload or not isinstance(payload.get("refresh_token"), str) or not payload["refresh_token"]:
        _emit(
            {
                "command": "hb-assistant procore auth refresh",
                "ok": False,
                "kind": "oauth_refresh_unavailable",
                "reason": "no_refresh_token_in_cache",
                "guardrails": _GUARDRAILS,
            },
            json_out=json_out,
            exit_code=1,
        )
        return
    client = _build_oauth_client()
    try:
        token_set = client.refresh_access_token(payload["refresh_token"])
        write_token_cache(token_set)
    except SecretNotAvailableError:
        _emit(
            {
                "command": "hb-assistant procore auth refresh",
                "ok": False,
                "kind": "secret_not_configured",
                "reason": "no_client_secret_in_keychain_env_or_protected_file",
                "hint": (
                    "Install the Procore client secret with: "
                    "security add-generic-password -U "
                    "-s 'hb-assistant-procore' -a 'client-secret' -w '<value>'"
                ),
                "guardrails": _GUARDRAILS,
            },
            json_out=json_out,
            exit_code=1,
        )
        return
    except ProcoreOAuthError as exc:
        _emit(
            {
                "command": "hb-assistant procore auth refresh",
                "ok": False,
                "kind": "oauth_refresh_failed",
                "status": int(exc.status),
                "correlation_id": exc.correlation_id,
                "guardrails": _GUARDRAILS,
            },
            json_out=json_out,
            exit_code=1,
        )
        return
    out = _redacted_oauth_envelope(
        "hb-assistant procore auth refresh",
        kind="oauth_refresh",
        token_set=token_set,
    )
    _emit(out, json_out=json_out)


@auth_app.command("logout")
def auth_logout(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Remove the local OAuth token cache (does not contact Procore)."""
    from hb_assistant.procore.token_provider import clear_token_cache

    removed = clear_token_cache()
    _emit(
        {
            "command": "hb-assistant procore auth logout",
            "ok": True,
            "kind": "oauth_logout",
            "removed": removed,
            "guardrails": _GUARDRAILS,
        },
        json_out=json_out,
    )


def _load_contract_or_emit(json_out: bool) -> Any:
    try:
        return load_endpoint_contract()
    except EndpointContractError as e:
        _emit(
            {
                "command": "hb-assistant procore",
                "status": "endpoint_contract_unavailable",
                "error": str(e),
            },
            json_out=json_out,
            exit_code=1,
        )
    except ValidationError as e:
        _emit(
            {
                "command": "hb-assistant procore",
                "status": "endpoint_contract_invalid",
                "error": f"{len(e.errors())} validation error(s)",
            },
            json_out=json_out,
            exit_code=1,
        )


def _load_projects_or_emit(json_out: bool) -> Any:
    try:
        return load_procore_projects()
    except ProcoreProjectsError as e:
        _emit(
            {
                "command": "hb-assistant procore",
                "status": "projects_registry_unavailable",
                "error": str(e),
            },
            json_out=json_out,
            exit_code=1,
        )
    except ValidationError as e:
        _emit(
            {
                "command": "hb-assistant procore",
                "status": "projects_registry_invalid",
                "error": f"{len(e.errors())} validation error(s)",
            },
            json_out=json_out,
            exit_code=1,
        )


@tools_app.command("list")
def tools_list(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List every endpoint in the loaded Procore contract."""

    contract = _load_contract_or_emit(json_out)
    rows = [e.model_dump() for e in contract.endpoints]
    by_status: dict[str, int] = {}
    for e in contract.endpoints:
        by_status[e.status] = by_status.get(e.status, 0) + 1
    payload = {
        "command": "hb-assistant procore tools list",
        "company_id": contract.company_id,
        "company_display_name": contract.company_display_name,
        "version": contract.version,
        "endpoint_count": len(rows),
        "by_status": by_status,
        "endpoints": rows,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@tools_app.command("catalog")
def tools_catalog(
    json_out: bool = typer.Option(True, "--json"),
    include_ineligible: bool = typer.Option(
        True,
        "--include-ineligible/--no-include-ineligible",
        help="Include endpoints that are not live-eligible (default). Pass --no-include-ineligible to filter to live-eligible only.",
    ),
) -> None:
    """Export the full Procore endpoint catalog with structured verification metadata.

    100% offline. No transport. No live calls. Surfaces every endpoint with its
    verification provenance fields (Phase 04 Prompt 03) plus the derived
    ``is_live_eligible`` flag and aggregate counts by verification status.
    """

    contract = _load_contract_or_emit(json_out)
    endpoints_out: list[dict[str, Any]] = []
    by_v: dict[str, int] = {}
    by_status: dict[str, int] = {}
    live_count = 0
    for ep in contract.endpoints:
        eligible = ep.is_live_eligible
        if not include_ineligible and not eligible:
            continue
        row = ep.model_dump()
        # Pydantic computed_field is included by default in v2 model_dump; defensive.
        row["is_live_eligible"] = eligible
        endpoints_out.append(row)
        by_v[ep.verification_status] = by_v.get(ep.verification_status, 0) + 1
        by_status[ep.status] = by_status.get(ep.status, 0) + 1
        if eligible:
            live_count += 1

    payload = {
        "command": "hb-assistant procore tools catalog",
        "schema_version": 1,
        "company_id": contract.company_id,
        "company_display_name": contract.company_display_name,
        "version": contract.version,
        "endpoint_count": len(endpoints_out),
        "include_ineligible": include_ineligible,
        "summary": {
            "by_verification_status": by_v,
            "by_status": by_status,
            "live_eligible_count": live_count,
        },
        "endpoints": endpoints_out,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@tools_app.command("audit")
def tools_audit(
    project: str = typer.Option(..., "--project", help="hb_project_key from procore_projects.seed.yaml."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Dry-run endpoint access audit for one HB project (no live call)."""

    contract = _load_contract_or_emit(json_out)
    projects = _load_projects_or_emit(json_out)

    auditor = EndpointAuditor(contract, projects)
    try:
        report = auditor.audit_project(project)
    except KeyError:
        _emit(
            {
                "command": "hb-assistant procore tools audit",
                "status": "not_found",
                "requested": project,
                "available": [p.hb_project_key for p in projects.projects],
            },
            json_out=json_out,
            exit_code=1,
        )

    payload = {
        "command": "hb-assistant procore tools audit",
        "mode": "dry_run",
        "report": report.model_dump(),
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@mapping_app.command("validate")
def mapping_validate(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Validate the Procore project mapping registry (informational; covers primary company context and pending pilots)."""

    contract = _load_contract_or_emit(json_out)
    projects = _load_projects_or_emit(json_out)

    auditor = EndpointAuditor(contract, projects)
    report = auditor.validate_mapping()
    payload = {
        "command": "hb-assistant procore mapping validate",
        "company_id": contract.company_id,
        "company_display_name": contract.company_display_name,
        "report": report.model_dump(),
        "guardrails": _GUARDRAILS,
    }
    # Exit 0 if every project is either a pilot-with-id or deprecated; exit
    # 1 (informational, not blocking) when pending rows (including pending pilots) remain — so CI /
    # health checks can choose to alert on incomplete mapping.
    _emit(payload, json_out=json_out, exit_code=0 if report.ok else 1)


@mapping_app.command("list")
def mapping_list(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List Procore project mappings (read-only; status coverage)."""

    contract = _load_contract_or_emit(json_out)
    projects = _load_projects_or_emit(json_out)

    auditor = EndpointAuditor(contract, projects)
    report = auditor.validate_mapping()
    payload = {
        "command": "hb-assistant procore mapping list",
        "company_id": contract.company_id,
        "report": report.model_dump(),
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@projects_app.command("list")
def projects_list(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List projects from Procore projects registry (read-only; status coverage)."""

    projects = _load_projects_or_emit(json_out)
    rows = [p.model_dump() for p in projects.projects]
    payload = {
        "command": "hb-assistant procore projects list",
        "project_count": len(rows),
        "projects": rows,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@companies_app.command("list")
def companies_list(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List company context from endpoint contract (read-only)."""

    contract = _load_contract_or_emit(json_out)
    payload = {
        "command": "hb-assistant procore companies list",
        "companies": [
            {
                "company_id": contract.company_id,
                "display_name": contract.company_display_name,
            }
        ],
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


# Prompt_07: audit subcommands (dry-run default; execute = explicit manual live opt-in only)
# All paths remain read-only, GET-only, redacted. Live never auto-invoked.


@audit_app.command("dry-run")
def audit_dry_run(
    project: str = typer.Option(..., "--project", help="hb_project_key from mapping"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Dry-run endpoint audit (default, no network). Constructs requests + verdicts + redacted receipt."""

    contract = _load_contract_or_emit(json_out)
    projects = _load_projects_or_emit(json_out)

    auditor = EndpointAuditor(contract, projects)
    # Base URL from contract or known env (sanitized; real value injected at runtime via Prompt_02)
    base = "https://api.procore.com"  # placeholder; production uses env config
    receipt: EndpointAuditRunReceipt = auditor.build_audit_run_receipt(
        project,
        base_url=base,
        mode="dry_run",
    )
    payload = {
        "command": "hb-assistant procore audit dry-run",
        "receipt": receipt.model_dump(),
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@audit_app.command("execute")
def audit_execute(
    project: str = typer.Option(..., "--project"),
    json_out: bool = typer.Option(True, "--json"),
    confirm: bool = typer.Option(False, "--confirm", help="Explicit opt-in for manual live GET (Bobby-only, never in tests/CI)"),
) -> None:
    """EXPLICIT MANUAL LIVE audit only. Opt-in required. Still GET-only + fully redacted. Never default."""

    if not confirm:
        typer.echo("ERROR: --confirm required for manual live audit (opt-in only). Dry-run is the safe default.", err=True)
        raise typer.Exit(1)

    try:
        require_live_env(command="procore audit execute")
    except LiveEnvNotSet as exc:
        typer.echo(f"ERROR: {exc.message}", err=True)
        raise typer.Exit(2) from None

    contract = _load_contract_or_emit(json_out)
    projects = _load_projects_or_emit(json_out)

    # In real usage the caller supplies a real Prompt_04 client here (with secret at call time only).
    # For CLI surface we document that this path is manual-only and redacted.
    auditor = EndpointAuditor(contract, projects)
    base = "https://api.procore.com"
    receipt = auditor.build_audit_run_receipt(
        project,
        base_url=base,
        mode="live_manual",
        # live_client would be passed in a real manual script / higher-level orchestrator
    )
    payload = {
        "command": "hb-assistant procore audit execute (manual live opt-in)",
        "receipt": receipt.model_dump(),
        "guardrails": _GUARDRAILS,
        "warning": "This was an explicit manual live invocation. Bodies and secrets redacted by default.",
    }
    _emit(payload, json_out=json_out)


# =============================================================================
# Prompt_09: procore sync (dry-run default + explicit --apply to local SQLite only)
# =============================================================================

sync_app = typer.Typer(help="Pilot project dry-run sync pipeline (Prompt_09). Dry-run default. --apply is explicit opt-in, local SQLite only, audit-gated.")
live_app = typer.Typer(help="Phase 04A Prompt 03A live command contract (fail-closed; no live calls).")
live_endpoints_app = typer.Typer(help="List live endpoint command-contract states.")

@sync_app.command("run")
def sync_run(
    project: Optional[str] = typer.Option(None, "--project", help="HB pilot key or mapped project (default: all mapped pilots; pending requires --allow-pending)"),
    dry_run: bool = typer.Option(True, "--dry-run", help="Default: plan only, redacted, zero side effects"),
    apply: bool = typer.Option(False, "--apply", help="EXPLICIT opt-in only. Writes local SQLite normalized rows after audit gate. Never external."),
    full_refresh: bool = typer.Option(False, "--full-refresh"),
    json_out: bool = typer.Option(True, "--json"),
    confirm: bool = typer.Option(False, "--confirm", help="Required with --apply in non-TTY contexts"),
    allow_pending: bool = typer.Option(False, "--allow-pending", help="Explicit opt-in to target a project whose mapping status is 'pending'. Default fails closed."),
    endpoints: Optional[list[str]] = typer.Option(None, "--endpoints", "-e", help="Filter to one or more endpoint IDs (repeatable). Defaults to every endpoint in the contract."),  # noqa: B008
) -> None:
    """Dry-run (default) or apply (opt-in) for pilot projects.

    Audit prerequisite (Prompt_07 surfaces) is mandatory before any planning or execution.
    Pending mappings are rejected unless ``--allow-pending`` is set.
    All writes are local SQLite only (temp DB supported for validation). GET-only. Redacted.

    ``--endpoints`` is repeatable; pass once per endpoint id (e.g.
    ``--endpoints list-rfis -e list-submittals``). Phase 04 Prompt 04 introduces
    the canonical RFI normalizer; the dry-run receipt for ``list-rfis`` carries
    the normalization schema version and the children-persistence flag.
    """
    if apply and not confirm and not sys.stdin.isatty():
        typer.echo("ERROR: --confirm required for non-TTY --apply (guardrail).", err=True)
        raise typer.Exit(1)

    if apply and not confirm and not typer.confirm("CONFIRM: --apply will write to local SQLite only (no Procore mutation). Continue?", default=False):
        typer.echo("Aborted.")
        raise typer.Exit(1)

    if apply:
        try:
            require_live_env(command="procore sync run --apply")
        except LiveEnvNotSet as exc:
            typer.echo(f"ERROR: {exc.message}", err=True)
            raise typer.Exit(2) from None
        try:
            registry = load_procore_projects()
            target_keys = [project] if project else [
                p.hb_project_key for p in registry.projects if p.status == "pilot"
            ]
            assert_live_mapping_strict(registry, target_keys)
        except ProcoreAPIError as exc:
            typer.echo(f"ERROR: {exc.message}", err=True)
            raise typer.Exit(3) from None

    from hb_assistant.procore.sync import run_sync  # lazy, after guard checks

    result = run_sync(
        project_key=project,
        dry_run=dry_run and not apply,
        apply=apply,
        full_refresh=full_refresh,
        json_output=json_out,
        allow_pending=allow_pending,
        endpoints=endpoints or None,
    )
    _emit(result, json_out=json_out)


# Register the new sub-app (additive; existing surfaces untouched)
app.add_typer(sync_app, name="sync", help="Pilot project dry-run sync (Prompt_09) — audit-gated, local SQLite only")
app.add_typer(live_app, name="live", help="Live Procore command scaffolding (fail-closed)")
live_app.add_typer(live_endpoints_app, name="endpoints")

_LIVE_ENDPOINT_ALIAS_TO_ID: dict[str, str] = {
    "projects": "list-projects",
    "rfis": "list-rfis",
    "submittals": "list-submittals",
    "drawings": "list-drawings",
    "daily-logs": "list-daily-logs",
    "punch-items": "list-punch-items",
    "change-events": "list-change-events",
    "commitments": "list-commitments",
    "prime-contracts": "list-prime-contracts",
    "invoices": "list-invoices",
    "correspondence": "list-correspondence",
    "schedule": "list-schedule",
    "tasks": "list-tasks",
    "observations": "list-observations",
    "meetings": "list-meetings",
    "meeting-topics": "list-meeting-topics",
}
_SUPPORTED_ENDPOINT_IDS = {
    "list-rfis",
    "list-submittals",
    "list-observations",
    "list-meetings",
    "list-meeting-topics",
    "list-daily-logs",
}
_VERIFIED_FOR_LIVE = {"verified", "official_docs_verified"}


def _phase04a_endpoint_rows() -> list[dict[str, Any]]:
    """Build the canonical Phase 04A endpoint matrix rows for `endpoints list`."""
    from hb_assistant.procore import endpoints as ep_registry

    rows: list[dict[str, Any]] = []
    for adapter in ep_registry.list_all():
        rows.append(
            {
                "command_endpoint": adapter.endpoint_id,
                "endpoint_id": adapter.endpoint_id,
                "legacy_endpoint_alias": adapter.legacy_endpoint_alias,
                "family": adapter.family,
                "live_verified": adapter.live_verified,
                "verification_reason": adapter.verification_reason,
                "sensitivity": adapter.sensitivity,
                "review_required_default": adapter.review_required_default,
                "path_template": adapter.path_template,
                "sqlite_target": adapter.sqlite_target,
                "state": "live_eligible" if adapter.live_verified else "not_live_verified",
            }
        )
    return rows


def _resolve_project_mapping(project_key: str) -> tuple[Optional[str], list[str]]:
    errors: list[str] = []
    procore_project_id: Optional[str] = None
    try:
        registry = load_procore_projects()
        assert_live_mapping_strict(registry, [project_key])
        for row in registry.projects:
            if row.hb_project_key == project_key:
                value = (row.procore_project_id or "").strip()
                procore_project_id = value or None
                break
        if not procore_project_id:
            errors.append("procore_project_id_unresolved")
    except ProcoreAPIError:
        errors.append("mapping_not_live_eligible")
    except Exception:  # noqa: BLE001
        errors.append("mapping_registry_unavailable")
    return procore_project_id, errors


def _validate_non_repo_output_dir(output_dir: Path) -> tuple[bool, str]:
    from hb_assistant.config.path_policy import PathPolicy

    if not output_dir.is_absolute():
        return False, "output_dir_not_absolute"
    repo_root = PathPolicy().resolve_repo_root().resolve()
    candidate = output_dir.resolve()
    if candidate == repo_root or repo_root in candidate.parents:
        return False, "output_dir_inside_repo"
    return True, ""


def _top_level_shape_summary(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        first = payload[0] if payload else None
        return {
            "top_level_type": "list",
            "record_count": len(payload),
            "first_item_type": type(first).__name__ if first is not None else None,
            "first_item_keys": sorted(first.keys())[:20] if isinstance(first, dict) else None,
        }
    if isinstance(payload, dict):
        keys = sorted(payload.keys())
        return {
            "top_level_type": "dict",
            "key_count": len(keys),
            "keys": keys[:50],
        }
    return {"top_level_type": type(payload).__name__}


def _redact_known_sensitive_fields(payload: Any) -> Any:
    sensitive_keys = {
        "authorization",
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "token",
        "bearer",
    }
    if isinstance(payload, list):
        return [_redact_known_sensitive_fields(item) for item in payload]
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if key.lower() in sensitive_keys:
                out[key] = "[REDACTED]"
            else:
                out[key] = _redact_known_sensitive_fields(value)
        return out
    return payload


def _state_for_endpoint(ep: Any) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if ep.verification_status == "excluded_by_guardrail":
        return "fail_closed_unsupported", ["excluded_by_guardrail"]
    if ep.verification_status == "deferred_by_guardrail":
        return "fail_closed_unsupported", ["deferred_by_guardrail"]
    if not ep.is_live_eligible:
        reasons.append("not_live_verified")
    if ep.endpoint_id not in _SUPPORTED_ENDPOINT_IDS:
        reasons.append("adapter_missing")
        reasons.append("normalizer_missing")
        reasons.append("sqlite_upsert_missing")
    if ep.verification_status not in _VERIFIED_FOR_LIVE:
        reasons.append("not_live_verified")
    if reasons:
        state = "not_live_verified" if "not_live_verified" in reasons else "fail_closed_unsupported"
        return state, sorted(set(reasons))
    return "operational", []


@live_endpoints_app.command("list")
def live_endpoints_list(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    payload = {
        "command": "hb-assistant procore live endpoints list",
        "ok": True,
        "phase": "Phase 04A Prompt 03B",
        "endpoints": _phase04a_endpoint_rows(),
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_endpoints_app.command("ledger")
def live_endpoints_ledger(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Machine-readable endpoint promotion ledger (Phase 06B Prompt 01).

    Deterministic projection of the canonical registry: promotion status,
    evidence path, last-verified date, and next step per endpoint. Read-only;
    no live Procore call.
    """
    from hb_assistant.procore.endpoint_ledger import build_promotion_ledger

    payload = {**build_promotion_ledger(), "guardrails": _GUARDRAILS}
    _emit(payload, json_out=json_out)


@live_app.command("sync")
def live_sync(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id (e.g. rfis, submittals, projects, daily-log-weather)."),
    apply: bool = typer.Option(False, "--apply", help="Required for live intent."),
    sqlite_only: bool = typer.Option(True, "--sqlite-only", help="Required guardrail; no source-system mutation."),
    max_pages: int = typer.Option(3, "--max-pages", min=1),
    max_items: int = typer.Option(100, "--max-items", min=1),
    max_child_requests: int = typer.Option(
        50, "--max-child-requests", min=1,
        help="Bounded N+1 fan-out: max child GETs per run (one per parent). When reached, "
        "remaining parents are skipped and a later run backfills idempotently.",
    ),
    confirm_live_get: bool = typer.Option(False, "--confirm-live-get"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Optional ISO date (YYYY-MM-DD) date-window filter (daily-log sections)."),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="Optional ISO date (YYYY-MM-DD) date-window filter (daily-log sections)."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Per-endpoint live sync (Phase 04A Prompt 03B).

    Verified endpoints execute the full chain; unverified endpoints return a
    structured `not_live_verified` receipt with no API call and no DB write.

    Operator template:
    HB_PROCORE_LIVE=1 hb-assistant procore live sync --project tropical
      --endpoint rfis --apply --sqlite-only --max-pages 3 --max-items 100
      --confirm-live-get --json
    """
    from hb_assistant.procore.live_sync import run_live_sync

    receipt = run_live_sync(
        project_key=project,
        endpoint=endpoint,
        apply=apply,
        sqlite_only=sqlite_only,
        confirm_live_get=confirm_live_get,
        max_pages=max_pages,
        max_items=max_items,
        max_child_requests=max_child_requests,
        mode_hint="live_apply" if apply else "live_dry_run",
        evidence_path="docs/evidence/construction-intelligence-phase-04a/02-endpoint-command-matrix.md",
        start_date=start_date,
        end_date=end_date,
    )
    payload = {
        "command": "hb-assistant procore live sync",
        "ok": receipt["state"] == "success",
        "phase": "Phase 04A Prompt 03B",
        "guardrails": _GUARDRAILS,
        **receipt,
    }
    if receipt["state"] == "success":
        exit_code = 0
    elif receipt["state"] == "not_live_verified":
        exit_code = 2
    else:
        exit_code = 3
    _emit(payload, json_out=json_out, exit_code=exit_code)


@live_app.command("inspect")
def live_inspect(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id."),
    rfi_id: Optional[str] = typer.Option(None, "--rfi-id", help="Parent RFI id for rfi-responses."),
    submittal_id: Optional[str] = typer.Option(None, "--submittal-id", help="Parent submittal id for submittal-responses."),
    meeting_id: Optional[str] = typer.Option(None, "--meeting-id", help="Meeting id for meeting-detail."),
    schedule_id: Optional[str] = typer.Option(None, "--schedule-id", help="Schedule id for activities."),
    max_pages: int = typer.Option(1, "--max-pages", min=1),
    max_items: int = typer.Option(5, "--max-items", min=1),
    confirm_live_get: bool = typer.Option(False, "--confirm-live-get"),
    confirm_raw_payload_dump: bool = typer.Option(False, "--confirm-raw-payload-dump"),
    output_dir: Path = typer.Option(..., "--output-dir", help="Explicit absolute non-repo directory for raw payload dumps."),  # noqa: B008
    redact_known_sensitive_fields: bool = typer.Option(False, "--redact-known-sensitive-fields"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Operator-only payload inspection.

    Raw payload is written only to the explicit non-repo output dir.
    No raw payload is persisted to SQLite, evidence, Obsidian, logs, or repo files.
    """
    from hb_assistant.procore import endpoints as ep_registry
    from hb_assistant.procore.http_client import ProcoreHTTPClient
    from hb_assistant.procore.token_provider import default_procore_token_provider
    from hb_assistant.store.procore_repositories import get_first_procore_record_id

    reason_codes: list[str] = []
    adapter = ep_registry.get(endpoint)
    endpoint_id = adapter.endpoint_id if adapter is not None else None
    if adapter is None:
        reason_codes.append("endpoint_alias_unknown")

    if not confirm_live_get:
        reason_codes.append("confirm_live_get_required")
    if not confirm_raw_payload_dump:
        reason_codes.append("confirm_raw_payload_dump_required")
    try:
        require_live_env(command="procore live inspect")
    except LiveEnvNotSet:
        reason_codes.append("live_env_not_set")

    ok_dir, dir_reason = _validate_non_repo_output_dir(output_dir)
    if not ok_dir:
        reason_codes.append(dir_reason)

    project_id, mapping_errors = _resolve_project_mapping(project)
    reason_codes.extend(mapping_errors)

    if adapter is not None and not adapter.live_verified:
        reason_codes.append("endpoint_not_live_verified")

    path_params: dict[str, str] = {}
    parent_resolution_source = "unresolved"
    resolved_parent_endpoint_id: Optional[str] = None
    resolved_parent_id: Optional[str] = None
    if project_id:
        path_params["project_id"] = project_id
    path_params["company_id"] = "5280"
    if rfi_id:
        path_params["rfi_id"] = rfi_id
    if submittal_id:
        path_params["submittal_id"] = submittal_id
    if meeting_id:
        path_params["id"] = meeting_id
    if schedule_id:
        path_params["schedule_id"] = schedule_id

    parent_lookup_by_endpoint: dict[str, tuple[str, str]] = {
        "rfi-responses": ("rfi_id", "rfis"),
        "submittal-responses": ("submittal_id", "submittals"),
        "meeting-detail": ("id", "meetings"),
        "activities": ("schedule_id", "schedules"),
    }
    if adapter is not None:
        lookup = parent_lookup_by_endpoint.get(adapter.endpoint_id)
        if lookup is not None:
            parent_param, parent_endpoint_id = lookup
            resolved_parent_endpoint_id = parent_endpoint_id
            explicit_parent_id = path_params.get(parent_param)
            if explicit_parent_id:
                parent_resolution_source = "explicit_flag"
                resolved_parent_id = explicit_parent_id
            else:
                looked_up_parent_id = get_first_procore_record_id(
                    project_key=project,
                    endpoint_id=parent_endpoint_id,
                )
                if looked_up_parent_id:
                    path_params[parent_param] = looked_up_parent_id
                    parent_resolution_source = "sqlite_first_occurrence"
                    resolved_parent_id = looked_up_parent_id
                else:
                    reason_codes.append(
                        f"parent_record_not_found_in_sqlite:{parent_endpoint_id}"
                    )

    if adapter is not None:
        for param in adapter.required_path_params:
            if not path_params.get(param):
                reason_codes.append(f"missing_path_param:{param}")

    auth_report = check_auth_status()
    token_ready = bool(auth_report.ready_for_live_calls)
    if not token_ready:
        reason_codes.append("token_provider_unavailable")

    if reason_codes:
        payload = {
            "command": "hb-assistant procore live inspect",
            "ok": False,
            "phase": "Phase 04A Prompt 03B",
            "status": "fail_closed",
            "state": "fail_closed_unsupported",
            "reason_codes": sorted(set(reason_codes)),
            "command_endpoint": endpoint,
            "endpoint_id": endpoint_id,
            "project_key": project,
            "oauth_status": auth_report.status,
            "parent_resolution_source": parent_resolution_source,
            "resolved_parent_endpoint_id": resolved_parent_endpoint_id,
            "resolved_parent_id": resolved_parent_id,
            "request_count": 0,
            "attempt_count": 0,
            "retry_count": 0,
            "last_retry_after": None,
            "retrieved_count": 0,
            "normalized_count": 0,
            "sqlite_upsert_count": 0,
            "sqlite_total_count": 0,
            "record_count": 0,
            "output_file_path": None,
            "output_file_sha256": None,
            "top_level_shape_summary": None,
            "no_sqlite_write": True,
            "no_evidence_write": True,
            "no_obsidian_write": True,
            "no_live_call_performed": True,
            "guardrails": _GUARDRAILS,
        }
        _emit(payload, json_out=json_out, exit_code=3)
        return

    assert adapter is not None
    assert project_id is not None
    path = adapter.path_template
    for key, value in path_params.items():
        path = path.replace(f"{{{key}}}", value)
    request_params = None if "{project_id}" in adapter.path_template else {"project_id": project_id}

    transport_calls = {"count": 0}
    real_client = ProcoreHTTPClient(
        environment="production",
        transport=None,
        access_token_provider=default_procore_token_provider(),
        live_enabled=True,
    )

    def _recording_transport(method: str, url: str, headers: dict[str, str], params: Optional[dict[str, Any]] = None) -> Any:
        transport_calls["count"] += 1
        return real_client._default_live_transport(method, url, headers, params)  # type: ignore[attr-defined]

    client = ProcoreHTTPClient(
        environment="production",
        transport=_recording_transport,
        access_token_provider=default_procore_token_provider(),
        live_enabled=True,
    )

    try:
        rows = list(
            client.paginate(
                path,
                params=request_params,
                max_pages=max_pages,
                max_items=max_items,
                retry_policy=RetryPolicy(max_retries=0, jitter=False),
            )
        )
    except ProcoreAPIError as exc:
        attempt_count = transport_calls["count"]
        retry_count = max(0, attempt_count - 1)
        last_retry_after = exc.retry_after if isinstance(exc, ProcoreRateLimitError) else None
        reason = "transport_error:429_rate_limited" if exc.status == 429 else f"transport_error:{exc.status or exc.code or 'unknown'}"
        payload = {
            "command": "hb-assistant procore live inspect",
            "ok": False,
            "phase": "Phase 04A Prompt 03B",
            "status": "fail_closed",
            "state": "transport_error",
            "reason_codes": [reason],
            "command_endpoint": endpoint,
            "endpoint_id": adapter.endpoint_id,
            "project_key": project,
            "oauth_status": auth_report.status,
            "parent_resolution_source": parent_resolution_source,
            "resolved_parent_endpoint_id": resolved_parent_endpoint_id,
            "resolved_parent_id": resolved_parent_id,
            "request_count": attempt_count,
            "attempt_count": attempt_count,
            "retry_count": retry_count,
            "last_retry_after": last_retry_after,
            "retrieved_count": 0,
            "normalized_count": 0,
            "sqlite_upsert_count": 0,
            "sqlite_total_count": 0,
            "record_count": 0,
            "output_file_path": None,
            "output_file_sha256": None,
            "top_level_shape_summary": None,
            "no_sqlite_write": True,
            "no_evidence_write": True,
            "no_obsidian_write": True,
            "no_live_call_performed": False,
            "guardrails": _GUARDRAILS,
        }
        _emit(payload, json_out=json_out, exit_code=3)
        return
    raw_payload = rows
    serialized = json.dumps(raw_payload, indent=2, sort_keys=True, default=str)
    payload_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    short_hash = payload_sha256[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    output_dir.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        output_dir.chmod(0o700)

    output_file = output_dir / f"procore_raw_{project}_{endpoint}_{stamp}_{short_hash}.json"
    output_file.write_text(serialized, encoding="utf-8")
    with suppress(OSError):
        output_file.chmod(0o600)

    redacted_file_path: Optional[str] = None
    redacted_sha256: Optional[str] = None
    if redact_known_sensitive_fields:
        redacted_payload = _redact_known_sensitive_fields(raw_payload)
        redacted_serialized = json.dumps(redacted_payload, indent=2, sort_keys=True, default=str)
        redacted_sha256 = hashlib.sha256(redacted_serialized.encode("utf-8")).hexdigest()
        redacted_file = output_dir / f"procore_raw_{project}_{endpoint}_{stamp}_{short_hash}.redacted.json"
        redacted_file.write_text(redacted_serialized, encoding="utf-8")
        with suppress(OSError):
            redacted_file.chmod(0o600)
        redacted_file_path = str(redacted_file)

    payload = {
        "command": "hb-assistant procore live inspect",
        "ok": True,
        "phase": "Phase 04A Prompt 03B",
        "status": "success",
        "state": "success",
        "reason_codes": [],
        "command_endpoint": endpoint,
        "endpoint_id": adapter.endpoint_id,
        "project_key": project,
        "oauth_status": auth_report.status,
        "parent_resolution_source": parent_resolution_source,
        "resolved_parent_endpoint_id": resolved_parent_endpoint_id,
        "resolved_parent_id": resolved_parent_id,
        "request_count": transport_calls["count"],
        "attempt_count": transport_calls["count"],
        "retry_count": max(0, transport_calls["count"] - 1),
        "last_retry_after": None,
        "retrieved_count": len(rows),
        "normalized_count": 0,
        "sqlite_upsert_count": 0,
        "sqlite_total_count": 0,
        "record_count": len(rows),
        "output_file_path": str(output_file),
        "output_file_sha256": payload_sha256,
        "redacted_output_file_path": redacted_file_path,
        "redacted_output_file_sha256": redacted_sha256,
        "top_level_shape_summary": _top_level_shape_summary(raw_payload),
        "no_sqlite_write": True,
        "no_evidence_write": True,
        "no_obsidian_write": True,
        "no_live_call_performed": False,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out, exit_code=0)


@live_app.command("smoke")
def live_smoke(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id."),
    max_pages: int = typer.Option(1, "--max-pages", min=1),
    max_items: int = typer.Option(10, "--max-items", min=1),
    confirm_live_get: bool = typer.Option(False, "--confirm-live-get"),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Optional ISO date (YYYY-MM-DD) date-window filter (daily-log sections)."),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="Optional ISO date (YYYY-MM-DD) date-window filter (daily-log sections)."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Smoke a verified endpoint without writing to SQLite. Live GET only."""
    from hb_assistant.procore.live_sync import run_live_sync

    receipt = run_live_sync(
        project_key=project,
        endpoint=endpoint,
        apply=False,
        sqlite_only=False,
        confirm_live_get=confirm_live_get,
        max_pages=max_pages,
        max_items=max_items,
        mode_hint="live_smoke",
        evidence_path="docs/evidence/construction-intelligence-phase-04a/01-live-transport-token-proof.md",
        start_date=start_date,
        end_date=end_date,
    )
    payload = {
        "command": "hb-assistant procore live smoke",
        "ok": receipt["state"] == "success",
        "phase": "Phase 04A Prompt 03B",
        "guardrails": _GUARDRAILS,
        **receipt,
    }
    if receipt["state"] == "success":
        exit_code = 0
    elif receipt["state"] == "not_live_verified":
        exit_code = 2
    else:
        exit_code = 3
    _emit(payload, json_out=json_out, exit_code=exit_code)


# --------------------------------------------------------------------------- #
# Phase 04B Prompt 10 — read-only local second-brain query commands.
# All are local SQLite / local-file only: no Procore call, no live gate, no token.
# --------------------------------------------------------------------------- #

_QUERY_PHASE = "Phase 04B Prompt 10"


def _query_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_endpoint_id(endpoint: Optional[str]) -> tuple[Optional[str], list[str]]:
    """Resolve an optional endpoint alias to a canonical id (read-only)."""
    if endpoint is None:
        return None, []
    from hb_assistant.procore import endpoints as ep_registry

    adapter = ep_registry.get(endpoint)
    if adapter is None:
        return None, ["endpoint_alias_unknown"]
    return adapter.endpoint_id, []


@live_app.command("history")
def live_history(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id (e.g. rfis)."),
    record_id: str = typer.Option(..., "--record-id", help="Procore record id."),
    parent_id: Optional[str] = typer.Option(None, "--parent-id", help="Parent procore id for child endpoints."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Reconstruct one record's history (snapshots + field-level change events). Local SQLite only."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_history import get_procore_changes, get_procore_record_history

    endpoint_id, reasons = _resolve_endpoint_id(endpoint)
    if endpoint_id is None:
        _emit({"command": "hb-assistant procore live history", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "state": "fail_closed_unsupported", "reason_codes": reasons}, json_out=json_out, exit_code=3)
        return
    SQLiteMigrator().apply()
    record_key = "|".join([project, endpoint_id, parent_id or "", str(record_id)])
    snapshots = get_procore_record_history(record_key=record_key)
    changes = get_procore_changes(project_key=project, record_key=record_key)
    payload = {
        "command": "hb-assistant procore live history", "ok": True, "phase": _QUERY_PHASE,
        "project_key": project, "endpoint_id": endpoint_id, "procore_record_id": str(record_id),
        "record_key": record_key, "snapshot_count": len(snapshots), "change_count": len(changes),
        "snapshots": [
            {k: s[k] for k in ("observed_at_utc", "source_updated_at_utc", "canonical_hash",
                               "changed_from_previous", "change_summary_json", "normalizer_version")}
            for s in snapshots
        ],
        "changes": changes,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_app.command("changes")
def live_changes(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    since: str = typer.Option(..., "--since", help='Relative ("48 hours ago", "7 days ago") or ISO timestamp.'),
    until: Optional[str] = typer.Option(None, "--until", help="Optional upper bound (relative or ISO)."),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="Optional endpoint filter."),
    record_id: Optional[str] = typer.Option(None, "--record-id", help="Optional single-record filter."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List field-level change events for a project since a time. Local SQLite only."""
    from hb_assistant.procore.time_window import parse_since
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_history import get_procore_changes

    endpoint_id, reasons = _resolve_endpoint_id(endpoint)
    now = _query_now()
    try:
        since_utc = parse_since(since, now=now)
        until_utc = parse_since(until, now=now) if until else None
    except ValueError:
        reasons.append("since_unparseable")
    if reasons:
        _emit({"command": "hb-assistant procore live changes", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "state": "fail_closed_unsupported", "reason_codes": reasons}, json_out=json_out, exit_code=3)
        return
    SQLiteMigrator().apply()
    record_key = "|".join([project, endpoint_id, "", str(record_id)]) if (endpoint_id and record_id) else None
    rows = get_procore_changes(project_key=project, since_utc=since_utc, until_utc=until_utc, record_key=record_key)
    if endpoint_id and record_key is None:
        rows = [r for r in rows if r.get("endpoint_id") == endpoint_id]
    payload = {
        "command": "hb-assistant procore live changes", "ok": True, "phase": _QUERY_PHASE,
        "project_key": project, "since_utc": since_utc, "until_utc": until_utc,
        "endpoint_id": endpoint_id, "change_count": len(rows), "changes": rows, "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_app.command("timeline")
def live_timeline(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    since: str = typer.Option(..., "--since", help='Relative ("7 days ago") or ISO timestamp.'),
    until: Optional[str] = typer.Option(None, "--until", help="Optional upper bound (relative or ISO)."),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="Optional endpoint filter."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List assistant-ready timeline events for a project since a time. Local SQLite only."""
    from hb_assistant.procore.time_window import parse_since
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_history import get_procore_timeline

    endpoint_id, reasons = _resolve_endpoint_id(endpoint)
    now = _query_now()
    try:
        since_utc = parse_since(since, now=now)
        until_utc = parse_since(until, now=now) if until else None
    except ValueError:
        reasons.append("since_unparseable")
    if reasons:
        _emit({"command": "hb-assistant procore live timeline", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "state": "fail_closed_unsupported", "reason_codes": reasons}, json_out=json_out, exit_code=3)
        return
    SQLiteMigrator().apply()
    rows = get_procore_timeline(project_key=project, since_utc=since_utc, until_utc=until_utc, endpoint_id=endpoint_id)
    payload = {
        "command": "hb-assistant procore live timeline", "ok": True, "phase": _QUERY_PHASE,
        "project_key": project, "since_utc": since_utc, "until_utc": until_utc,
        "endpoint_id": endpoint_id, "event_count": len(rows), "timeline": rows, "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_app.command("actions")
def live_actions(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    status: Optional[str] = typer.Option(None, "--status", help="Signal status filter (e.g. open, resolved)."),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="Optional endpoint filter."),
    importance: Optional[str] = typer.Option(None, "--importance", help="Optional importance filter (high/medium/low)."),
    signal_type: Optional[str] = typer.Option(None, "--signal-type", help="Optional signal-type filter."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List open/relevant action signals for a project. Local SQLite only."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_enrichment import get_procore_action_signals

    endpoint_id, reasons = _resolve_endpoint_id(endpoint)
    if reasons:
        _emit({"command": "hb-assistant procore live actions", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "state": "fail_closed_unsupported", "reason_codes": reasons}, json_out=json_out, exit_code=3)
        return
    SQLiteMigrator().apply()
    rows = get_procore_action_signals(
        project_key=project, signal_status=status, endpoint_id=endpoint_id,
        importance=importance, signal_type=signal_type,
    )
    payload = {
        "command": "hb-assistant procore live actions", "ok": True, "phase": _QUERY_PHASE,
        "project_key": project, "filters": {"status": status, "endpoint_id": endpoint_id,
                                            "importance": importance, "signal_type": signal_type},
        "action_count": len(rows), "actions": rows, "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_app.command("project-health")
def live_project_health(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    stale_days: int = typer.Option(7, "--stale-days", min=1, help="Endpoint freshness threshold."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Deterministic project-health read model over local SQLite (Phase 06B Prompt 06).

    Aggregates freshness, open work, review-required items, cost/schedule/safety-quality-
    compliance signal counts, and relationship-quality indicators. Review-required and
    high-risk facts are listed explicitly (never hidden behind a single score). Read-only;
    no network, no DB writes, no raw values, no determinations."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_project_health import build_project_health

    SQLiteMigrator().apply()
    report = build_project_health(project, now_utc=_query_now().isoformat(), stale_days=stale_days)
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("stale")
def live_stale(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    stale_days: int = typer.Option(7, "--stale-days", min=1, help="Endpoint freshness threshold."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Endpoint/project freshness — current / stale / never_synced / fail_closed / unknown per
    endpoint, with recommended sync commands for stale operational endpoints (Phase 06B Prompt 07).
    Read-only over local SQLite (watermarks / sync runs / record timestamps); no network, no writes.
    Held (fail-closed) endpoints are never counted as stale operational endpoints."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_freshness import build_freshness_report

    SQLiteMigrator().apply()
    report = build_freshness_report(project, now_utc=_query_now().isoformat(), stale_days=stale_days)
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("coverage")
def live_coverage(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key (contextual)."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id."),
    raw_payload: Path = typer.Option(..., "--raw-payload", help="Local JSON payload file (read-only; not persisted)."),  # noqa: B008
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report normalizer field coverage for a local raw payload (names/types only). No network, no DB."""
    from hb_assistant.procore.coverage import compute_payload_coverage

    endpoint_id, reasons = _resolve_endpoint_id(endpoint)
    if endpoint_id is None:
        _emit({"command": "hb-assistant procore live coverage", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "state": "fail_closed_unsupported", "reason_codes": reasons}, json_out=json_out, exit_code=3)
        return
    try:
        data = json.loads(Path(raw_payload).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _emit({"command": "hb-assistant procore live coverage", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "endpoint_id": endpoint_id, "state": "fail_closed_unsupported",
               "reason_codes": ["raw_payload_unreadable"]}, json_out=json_out, exit_code=3)
        return
    try:
        report = compute_payload_coverage(endpoint_id, data, now_utc=_query_now().isoformat())
    except ValueError:
        _emit({"command": "hb-assistant procore live coverage", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "endpoint_id": endpoint_id, "state": "fail_closed_unsupported",
               "reason_codes": ["coverage_compute_failed"]}, json_out=json_out, exit_code=3)
        return
    payload = {
        "command": "hb-assistant procore live coverage", "ok": True, "phase": _QUERY_PHASE,
        "project_key": project, **report, "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_app.command("coverage-matrix")
def live_coverage_matrix(
    payloads_dir: Optional[Path] = typer.Option(  # noqa: B008
        None, "--payloads-dir",
        help="Optional dir of local <endpoint_id>.json samples (e.g. `procore live inspect` "
        "output). Read-only; never persisted. Endpoints with a sample get captured/hash-only/"
        "omitted field NAMES; the rest are contract-only.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Endpoint coverage matrix by family (Phase 06B Prompt 05) — normalizer name/version,
    projected entities/edges/signals, and (where a sample is supplied) captured / hash-only /
    intentionally-omitted field names. Names/types/counts only; no raw values. No network, no DB."""
    from hb_assistant.procore.coverage import build_coverage_matrix

    if payloads_dir is not None and not payloads_dir.is_dir():
        _emit({"command": "hb-assistant procore live coverage-matrix", "ok": False,
               "phase": _QUERY_PHASE, "state": "fail_closed_unsupported",
               "reason_codes": ["payloads_dir_not_found"]}, json_out=json_out, exit_code=3)
        return
    matrix = build_coverage_matrix(payloads_dir=payloads_dir, now_utc=_query_now().isoformat())
    _emit({**matrix, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("overdue")
def live_overdue(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    importance: Optional[str] = typer.Option(
        None, "--importance", help="Optional importance filter (high/medium/low)."
    ),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="Optional endpoint filter."),
    dimension: Optional[str] = typer.Option(
        None, "--dimension",
        help="Optional dimension filter "
        "(cost_exposure/schedule_exposure/safety_quality_compliance/overdue).",
    ),
    max_items: int = typer.Option(50, "--max-items", min=1, help="Max queue rows returned."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Operational overdue/action queue across controls, financials, schedule, safety/quality,
    and review-required signals (Phase 06B Prompt 08). Each row carries endpoint, record key,
    due date + overdue status, importance, owner/responsible-party key, review flag, reason
    codes, dimensions, and exposure-fact NAMES. Read-only over local SQLite; no network, no DB
    writes, no raw values, no determinations."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_action_queue import build_overdue_queue

    endpoint_id, reasons = _resolve_endpoint_id(endpoint)
    if reasons:
        _emit({"command": "hb-assistant procore live overdue", "ok": False, "phase": _QUERY_PHASE,
               "project_key": project, "state": "fail_closed_unsupported", "reason_codes": reasons},
              json_out=json_out, exit_code=3)
        return
    SQLiteMigrator().apply()
    report = build_overdue_queue(
        project, now_utc=_query_now().isoformat(),
        importance=importance, endpoint_id=endpoint_id, dimension=dimension, max_items=max_items,
    )
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("responsible-party-gaps")
def live_responsible_party_gaps(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: Optional[str] = typer.Option(
        None, "--endpoint", help="Optional canonical endpoint_id filter."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Per-endpoint responsibility-edge coverage (Phase 06B Prompt 11) — owner (created_by),
    assignee, ball-in-court, responsible-contractor, vendor, and location. Reports covered /
    partial_gap / not_observed per (endpoint, relationship); a relationship never seen on an
    endpoint is not_observed (never a fabricated gap). Read-only over local SQLite; no network,
    no DB writes, no raw values, no determinations."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_relationship_quality import build_responsible_party_gaps

    SQLiteMigrator().apply()
    report = build_responsible_party_gaps(
        project, now_utc=_query_now().isoformat(), endpoint_id=endpoint,
    )
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("relationship-quality")
def live_relationship_quality(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    max_items: int = typer.Option(50, "--max-items", min=1, help="Max orphan sample rows."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Relationship-quality diagnostics (Phase 06B Prompt 11) — orphaned child records, parent/child
    linkage coverage, and commitment/PO duplicate warnings. Linkage that cannot be inferred is
    reported unknown (never guessed); dedupe covers only repo-supported commitment/PO surfaces.
    Read-only over local SQLite; no network, no DB writes, no raw values, no determinations."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_relationship_quality import build_relationship_quality

    SQLiteMigrator().apply()
    report = build_relationship_quality(
        project, now_utc=_query_now().isoformat(), max_items=max_items,
    )
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("digest")
def live_digest(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Operator digest (Phase 06B Prompt 12) — one compact roll-up of health status plus headline
    counts composed from the project-health, overdue, cost/schedule-exposure, responsible-party-gaps,
    and relationship-quality read models. Local SQLite only; read-only; no live call, no DB writes,
    no raw values, no determinations."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_operational import build_operational_digest

    SQLiteMigrator().apply()
    report = build_operational_digest(project, now_utc=_query_now().isoformat())
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("risks")
def live_risks(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    max_items: int = typer.Option(25, "--max-items", min=1, help="Max risk rows returned."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Top operational risks (Phase 06B Prompt 12) — open action signals that are high-importance or
    carry a cost/schedule/safety-quality/overdue dimension, ordered high-importance-first with
    per-dimension counts. Local SQLite only; read-only; no live call, no DB writes, no raw values,
    no determinations."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_operational import build_risks

    SQLiteMigrator().apply()
    report = build_risks(project, now_utc=_query_now().isoformat(), max_items=max_items)
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("retrieval-ready")
def live_retrieval_ready(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Retrieval-readiness probe (Phase 06B Prompt 12, preliminary) — counts the local retrievable
    corpus (text-intelligence, live records, open signals) and reports a ready flag with reasons.
    Local SQLite only; read-only; no live call, no DB writes, no raw values. Prompt 14 hardens true
    embedding readiness."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_operational import build_retrieval_readiness

    SQLiteMigrator().apply()
    report = build_retrieval_readiness(project, now_utc=_query_now().isoformat())
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_app.command("no-writeback-proof")
def live_no_writeback_proof(
    project: Optional[str] = typer.Option(None, "--project", help="Optional mapped project key."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """No-writeback posture attestation (Phase 06B Prompt 12, preliminary) — asserts the operator
    query surface is local SQLite only with no Microsoft 365 / Procore writeback and no raw-body
    persistence. Local SQLite only; read-only. Prompt 15 produces the formal no-writeback proof
    bundle."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_operational import build_no_writeback_proof

    SQLiteMigrator().apply()
    report = build_no_writeback_proof(project, now_utc=_query_now().isoformat())
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


live_records_app = typer.Typer(help="Procore live SQLite record read-only commands.")
live_app.add_typer(live_records_app, name="records")

# =============================================================================
# Phase 05 Prompt 11: procore live financial <verb> — local-only financial query
# commands over the V8/V9 financial tables + signals + history. No network, no
# token, no live gate; SQLite read-only.
# =============================================================================

live_financial_app = typer.Typer(
    help="Phase 05 financial read-only queries (contracts, changes, invoices, budget, "
    "risk, coverage). Local SQLite only — never calls Procore."
)
live_app.add_typer(live_financial_app, name="financial")

_FINANCIAL_PHASE = "Phase 05 Prompt 11"


@live_financial_app.command("summary")
def live_financial_summary(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Financial roll-up: contract summary + per-family counts. Local SQLite only."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_enrichment import get_procore_action_signals
    from hb_assistant.store.procore_financials import (
        read_financial_budget_changes,
        read_financial_change_events,
        read_financial_contract_summary,
        read_financial_rfqs,
        read_financial_subcontractor_invoices,
    )

    SQLiteMigrator().apply()
    contracts = read_financial_contract_summary(project_key=project)
    families: dict[str, int] = {}
    for c in contracts:
        families[c.get("contract_family") or "unknown"] = (
            families.get(c.get("contract_family") or "unknown", 0) + 1
        )
    open_signals = get_procore_action_signals(project_key=project, signal_status="open")
    payload = {
        "command": "hb-assistant procore live financial summary",
        "ok": True,
        "phase": _FINANCIAL_PHASE,
        "project_key": project,
        "counts": {
            "contracts": len(contracts),
            "contracts_by_family": families,
            "subcontractor_invoices": len(
                read_financial_subcontractor_invoices(project_key=project)
            ),
            "rfqs": len(read_financial_rfqs(project_key=project)),
            "change_events": len(read_financial_change_events(project_key=project)),
            "budget_changes": len(read_financial_budget_changes(project_key=project)),
            "open_financial_actions": len(open_signals),
        },
        "contracts": contracts,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_financial_app.command("contracts")
def live_financial_contracts(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    contract_type: Optional[str] = typer.Option(
        None, "--type", help="Filter by family: prime | commitment | purchase_order."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List financial contracts (optionally filtered by family). Local SQLite only."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_financials import read_financial_contract_summary

    SQLiteMigrator().apply()
    rows = read_financial_contract_summary(project_key=project)
    if contract_type is not None:
        rows = [r for r in rows if r.get("contract_family") == contract_type]
    payload = {
        "command": "hb-assistant procore live financial contracts",
        "ok": True,
        "phase": _FINANCIAL_PHASE,
        "project_key": project,
        "filters": {"type": contract_type},
        "contract_count": len(rows),
        "contracts": rows,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_financial_app.command("changes")
def live_financial_changes(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    since: str = typer.Option("30 days ago", "--since", help="Relative or ISO change window."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Financial change history within a window (field-level). Local SQLite only."""
    from hb_assistant.procore.financial_register import _FINANCIAL_ENDPOINTS
    from hb_assistant.procore.time_window import parse_since
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_history import get_procore_changes

    now = datetime.now(timezone.utc)
    try:
        since_utc = parse_since(since, now=now)
    except ValueError:
        _emit(
            {
                "command": "hb-assistant procore live financial changes",
                "ok": False,
                "phase": _FINANCIAL_PHASE,
                "project_key": project,
                "state": "fail_closed_unsupported",
                "reason_codes": ["since_unparseable"],
            },
            json_out=json_out,
            exit_code=3,
        )
        return
    SQLiteMigrator().apply()
    rows = [
        c
        for c in get_procore_changes(project_key=project, since_utc=since_utc)
        if c.get("endpoint_id") in _FINANCIAL_ENDPOINTS
    ]
    payload = {
        "command": "hb-assistant procore live financial changes",
        "ok": True,
        "phase": _FINANCIAL_PHASE,
        "project_key": project,
        "filters": {"since_utc": since_utc},
        "change_count": len(rows),
        "changes": rows,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_financial_app.command("invoices")
def live_financial_invoices(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    status: Optional[str] = typer.Option(
        None, "--status", help="Filter by status: approved | pending | paid | ..."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List subcontractor invoices (optionally filtered by status). Local SQLite only."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_financials import read_financial_subcontractor_invoices

    SQLiteMigrator().apply()
    rows = read_financial_subcontractor_invoices(project_key=project, status=status)
    payload = {
        "command": "hb-assistant procore live financial invoices",
        "ok": True,
        "phase": _FINANCIAL_PHASE,
        "project_key": project,
        "filters": {"status": status},
        "invoice_count": len(rows),
        "invoices": rows,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_financial_app.command("budget")
def live_financial_budget(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    view_id: Optional[str] = typer.Option(None, "--view-id", help="Filter to one budget view id."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Budget detail rows + changes (optionally one view). Local SQLite only."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_financial_projection import record_key
    from hb_assistant.store.procore_financials import (
        read_financial_budget_changes,
        read_financial_budget_rows,
    )

    SQLiteMigrator().apply()
    budget_view_key = (
        record_key(project, "budget-views", None, view_id) if view_id is not None else None
    )
    rows = read_financial_budget_rows(project_key=project, budget_view_key=budget_view_key)
    payload = {
        "command": "hb-assistant procore live financial budget",
        "ok": True,
        "phase": _FINANCIAL_PHASE,
        "project_key": project,
        "filters": {"view_id": view_id},
        "row_count": len(rows),
        "rows": rows,
        "changes": read_financial_budget_changes(project_key=project),
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_financial_app.command("risk")
def live_financial_risk(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Derived financial risk view (unexecuted contracts / unpaid change orders)."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_financials import read_financial_risk_view

    SQLiteMigrator().apply()
    rows = read_financial_risk_view(project_key=project)
    payload = {
        "command": "hb-assistant procore live financial risk",
        "ok": True,
        "phase": _FINANCIAL_PHASE,
        "project_key": project,
        "risk_count": len(rows),
        "risks": rows,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


@live_financial_app.command("exposure")
def live_financial_exposure(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    exposure_type: Optional[str] = typer.Option(
        None, "--type",
        help="Optional exposure-type filter (pending_change/unapproved_change/budget_movement/"
        "invoice_retainage_risk/rfq_quote_pending/compliance_risk/amount_changed).",
    ),
    importance: Optional[str] = typer.Option(
        None, "--importance", help="Optional importance filter (high/medium/low)."
    ),
    max_items: int = typer.Option(100, "--max-items", min=1, help="Max exposure rows returned."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Cost/financial exposure model (Phase 06B Prompt 09) — classifies open financial signals
    + budget changes into pending-change / unapproved-change / budget-movement / invoice-retainage
    / RFQ-quote-pending / compliance-risk / amount-changed exposure, each with decimal-safe string
    amounts, source link, and a review-required flag on high-sensitivity items. Advisory/review aid
    only — no entitlement/liability/contractual determinations; amounts are never summed. Read-only
    over local SQLite; no network, no DB writes, no raw values."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_cost_exposure import build_cost_exposure

    SQLiteMigrator().apply()
    report = build_cost_exposure(
        project, now_utc=_query_now().isoformat(),
        exposure_type=exposure_type, importance=importance, max_items=max_items,
    )
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_financial_app.command("coverage")
def live_financial_coverage(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical financial endpoint id."),
    raw_payload: str = typer.Option(
        ..., "--raw-payload", help="Path to a JSON file with a sample raw payload (offline)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Detect financial fields present in a raw payload but NOT captured by the
    endpoint normalizer. Offline (reads a file); never calls Procore."""
    import json as _json
    from pathlib import Path as _Path

    from hb_assistant.procore.live_sync import resolve_normalizer

    normalizer = resolve_normalizer(endpoint)
    if normalizer is None:
        _emit(
            {
                "command": "hb-assistant procore live financial coverage",
                "ok": False,
                "phase": _FINANCIAL_PHASE,
                "project_key": project,
                "endpoint_id": endpoint,
                "state": "fail_closed_unsupported",
                "reason_codes": ["endpoint_has_no_normalizer"],
            },
            json_out=json_out,
            exit_code=3,
        )
        return
    try:
        loaded = _json.loads(_Path(raw_payload).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _emit(
            {
                "command": "hb-assistant procore live financial coverage",
                "ok": False,
                "phase": _FINANCIAL_PHASE,
                "project_key": project,
                "endpoint_id": endpoint,
                "state": "fail_closed_unsupported",
                "reason_codes": ["raw_payload_unreadable"],
            },
            json_out=json_out,
            exit_code=3,
        )
        return
    record = loaded[0] if isinstance(loaded, list) and loaded else loaded
    raw_keys = [k for k, v in record.items() if not isinstance(v, (dict, list))] if isinstance(
        record, dict
    ) else []
    canonical = normalizer(
        record, project_key=project, endpoint_id=endpoint, correlation_id="coverage",
        fetched_at="1970-01-01T00:00:00Z",
    )["canonical_fields"]
    canonical_keys = set(canonical)
    omitted = [
        k for k in raw_keys
        if not any(ck == k or ck.startswith(f"{k}_") for ck in canonical_keys)
    ]
    payload = {
        "command": "hb-assistant procore live financial coverage",
        "ok": True,
        "phase": _FINANCIAL_PHASE,
        "project_key": project,
        "endpoint_id": endpoint,
        "raw_scalar_field_count": len(raw_keys),
        "captured_field_count": len(canonical_keys),
        "omitted_field_count": len(omitted),
        "omitted_fields": sorted(omitted),
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


live_schedule_app = typer.Typer(
    help="Phase 06B schedule exposure queries (RFIs, submittals, activities, meetings, punch, "
    "observations, inspections). Local SQLite only — never calls Procore."
)
live_app.add_typer(live_schedule_app, name="schedule")


@live_schedule_app.command("exposure")
def live_schedule_exposure(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    exposure_category: Optional[str] = typer.Option(
        None, "--type",
        help="Optional category filter (overdue_rfi/overdue_submittal/"
        "critical_or_low_float_activity/meeting_action_topic/inspection_punch_blocking/"
        "schedule_impact_flag).",
    ),
    importance: Optional[str] = typer.Option(
        None, "--importance", help="Optional importance filter (high/medium/low)."
    ),
    max_items: int = typer.Option(50, "--max-items", min=1, help="Max exposure rows returned."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Schedule exposure model (Phase 06B Prompt 10) — classifies open schedule-domain signals
    (overdue RFIs/submittals, low-float/critical activities, meeting action topics,
    inspection/punch/observation completion blockers, and schedule-impact flags) into exposure
    categories, each with reason codes, source link, due date + overdue status, and a
    review-required flag on high-sensitivity items. Advisory/review aid only — never asserts delay
    entitlement, responsibility, or schedule-impact determinations. Read-only over local SQLite;
    no network, no DB writes, no raw values."""
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_schedule_exposure import build_schedule_exposure

    SQLiteMigrator().apply()
    report = build_schedule_exposure(
        project, now_utc=_query_now().isoformat(),
        exposure_category=exposure_category, importance=importance, max_items=max_items,
    )
    _emit({**report, "guardrails": _GUARDRAILS}, json_out=json_out)


@live_records_app.command("count")
def live_records_count(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only count of procore_live_records rows for (project, endpoint)."""
    from hb_assistant.procore import endpoints as ep_registry
    from hb_assistant.store.migrator import SQLiteMigrator
    from hb_assistant.store.procore_repositories import count_procore_live_records

    adapter = ep_registry.get(endpoint)
    if adapter is None:
        payload = {
            "command": "hb-assistant procore live records count",
            "ok": False,
            "phase": "Phase 04A Prompt 03B",
            "command_endpoint": endpoint,
            "endpoint_id": None,
            "project_key": project,
            "state": "fail_closed_unsupported",
            "reason_codes": ["endpoint_alias_unknown"],
            "count": 0,
        }
        _emit(payload, json_out=json_out, exit_code=3)
        return

    SQLiteMigrator().apply()
    count = count_procore_live_records(project_key=project, endpoint_id=adapter.endpoint_id)
    payload = {
        "command": "hb-assistant procore live records count",
        "ok": True,
        "phase": "Phase 04A Prompt 03B",
        "command_endpoint": endpoint,
        "endpoint_id": adapter.endpoint_id,
        "legacy_endpoint_alias": adapter.legacy_endpoint_alias,
        "project_key": project,
        "count": count,
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)

# =============================================================================
# Prompt_10: procore obsidian output preview (dry-run default; explicit --apply)
# =============================================================================

@obsidian_app.command("preview")
def obsidian_preview(
    project: str = typer.Argument(..., help="HB project key (pilot/mapped from procore_projects.seed.yaml)"),
    dry_run: bool = typer.Option(True, "--dry-run", help="Default: paths + rendered Markdown (redacted samples), zero side effects"),
    apply: bool = typer.Option(False, "--apply", help="EXPLICIT opt-in only. Writes hybrid procore-*.md to 01_Projects/ + review note (local vault)."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Structured JSON envelope (default). Use --no-json for compact human-readable form."),
    confirm: bool = typer.Option(False, "--confirm", help="Required with --apply in non-TTY contexts"),
) -> None:
    """Procore Obsidian preview/apply (Prompt 10).

    Deterministic (non-LLM) Markdown from SQLite post-sync rows. Redaction + sensitive routing always on.
    Hybrid layout: procore-*.md files alongside legacy in 01_Projects/. Guardrails: no secrets ever.
    Default dry-run. --apply requires TTY confirm or --confirm (reuses sync/audit gate style).
    """
    if apply and not confirm and not sys.stdin.isatty():
        typer.echo("ERROR: --confirm required for non-TTY --apply (guardrail).", err=True)
        raise typer.Exit(1)
    if apply and not confirm and not typer.confirm(
        "CONFIRM: --apply will write procore-*.md (hybrid in 01_Projects/) + review note to local vault only (no Procore mutation). Continue?",
        default=False,
    ):
        typer.echo("Aborted.")
        raise typer.Exit(1)

    from hb_assistant.procore.obsidian import procore_obsidian_preview  # lazy import (per plan)

    result = procore_obsidian_preview(
        project_key=project,
        dry_run=dry_run and not apply,
        apply=apply,
        json_out=json_out,
    )

    # Structure per spec for CLI surface (command name, review_count, rendered_keys, redacted_errors)
    if isinstance(result, dict):
        result = dict(result)
        result["command"] = "procore obsidian preview"
        if "review_items" in result:
            result["review_count"] = len(result["review_items"])
        if "rendered" in result and isinstance(result["rendered"], dict):
            result["rendered_keys"] = list(result["rendered"])
        if "error" in result:
            result["redacted_errors"] = result["error"]

    _emit(result, json_out=json_out)


@obsidian_app.command("enriched")
def obsidian_enriched(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    since: str = typer.Option("48 hours ago", "--since", help='Window for the changes section (relative or ISO).'),
    dry_run: bool = typer.Option(True, "--dry-run", help="Default: rendered note preview, zero side effects."),
    apply: bool = typer.Option(False, "--apply", help="EXPLICIT opt-in. Writes one marker-bounded procore-memory-register.md to 01_Projects/ (local vault)."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Structured JSON envelope (default)."),
    confirm: bool = typer.Option(False, "--confirm", help="Required with --apply in non-TTY contexts."),
) -> None:
    """Phase 04B enriched second-brain register (open actions / changes / safety /
    schedule risk / meeting actions / RFI + submittal workflow). Read-only SQLite;
    never calls Procore. Dry-run default; --apply writes one marker-bounded note."""
    if apply and not confirm and not sys.stdin.isatty():
        typer.echo("ERROR: --confirm required for non-TTY --apply (guardrail).", err=True)
        raise typer.Exit(1)
    if apply and not confirm and not typer.confirm(
        "CONFIRM: --apply will write procore-memory-register.md to the local vault only (no Procore mutation). Continue?",
        default=False,
    ):
        typer.echo("Aborted.")
        raise typer.Exit(1)

    from hb_assistant.procore.obsidian_register import (
        apply_enriched_register,
        build_enriched_registers,
    )
    from hb_assistant.procore.time_window import parse_since

    now = datetime.now(timezone.utc)
    try:
        since_utc = parse_since(since, now=now)
    except ValueError:
        _emit({"command": "hb-assistant procore obsidian enriched", "ok": False, "phase": "Phase 04B Prompt 11",
               "project_key": project, "state": "fail_closed_unsupported", "reason_codes": ["since_unparseable"]},
              json_out=json_out, exit_code=3)
        return
    now_utc = now.isoformat().replace("+00:00", "Z")

    if apply:
        result = apply_enriched_register(project, since_utc=since_utc, now_utc=now_utc)
        if not result.get("vault_configured", False):
            _emit({"command": "hb-assistant procore obsidian enriched", "ok": False, "phase": "Phase 04B Prompt 11",
                   "project_key": project, "state": "fail_closed_unsupported",
                   "reason_codes": ["vault_root_unconfigured"]}, json_out=json_out, exit_code=3)
            return
    else:
        result = build_enriched_registers(project, since_utc=since_utc, now_utc=now_utc)
        result["written_paths"] = []

    payload = {
        "command": "hb-assistant procore obsidian enriched", "ok": True, "phase": "Phase 04B Prompt 11",
        "project_key": project, "mode": "apply" if apply else "dry_run", "dry_run": not apply,
        "since_utc": since_utc, "generated_utc": now_utc, "counts": result["counts"],
        "section_keys": list(result["sections"]), "rendered": result["rendered"],
        "written_paths": result["written_paths"], "guardrails": result["guardrails"],
    }
    _emit(payload, json_out=json_out)


@obsidian_app.command("financial")
def obsidian_financial(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    since: str = typer.Option(
        "30 days ago", "--since", help="Window for the recent-changes section (relative or ISO)."
    ),
    dry_run: bool = typer.Option(True, "--dry-run", help="Default: rendered note preview, zero side effects."),
    apply: bool = typer.Option(
        False, "--apply",
        help="EXPLICIT opt-in. Writes one marker-bounded procore-financial-register.md to 01_Projects/.",
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Structured JSON envelope (default)."),
    confirm: bool = typer.Option(False, "--confirm", help="Required with --apply in non-TTY contexts."),
) -> None:
    """Phase 05 financial register (contracts / change orders / commitments + compliance
    / invoices / payment applications / RFQs + change events / budget / retainage risk /
    recent changes). Read-only SQLite; never calls Procore. Dry-run default; --apply
    writes one marker-bounded source-linked note."""
    if apply and not confirm and not sys.stdin.isatty():
        typer.echo("ERROR: --confirm required for non-TTY --apply (guardrail).", err=True)
        raise typer.Exit(1)
    if apply and not confirm and not typer.confirm(
        "CONFIRM: --apply will write procore-financial-register.md to the local vault only "
        "(no Procore mutation). Continue?",
        default=False,
    ):
        typer.echo("Aborted.")
        raise typer.Exit(1)

    from hb_assistant.procore.financial_register import (
        apply_financial_register,
        build_financial_register,
    )
    from hb_assistant.procore.time_window import parse_since
    from hb_assistant.store.migrator import SQLiteMigrator

    now = datetime.now(timezone.utc)
    try:
        since_utc = parse_since(since, now=now)
    except ValueError:
        _emit(
            {
                "command": "hb-assistant procore obsidian financial", "ok": False,
                "phase": _FINANCIAL_PHASE, "project_key": project,
                "state": "fail_closed_unsupported", "reason_codes": ["since_unparseable"],
            },
            json_out=json_out, exit_code=3,
        )
        return
    now_utc = now.isoformat().replace("+00:00", "Z")
    SQLiteMigrator().apply()

    if apply:
        result = apply_financial_register(project, now_utc=now_utc, since_utc=since_utc)
        if not result.get("vault_configured", False):
            _emit(
                {
                    "command": "hb-assistant procore obsidian financial", "ok": False,
                    "phase": _FINANCIAL_PHASE, "project_key": project,
                    "state": "fail_closed_unsupported", "reason_codes": ["vault_root_unconfigured"],
                },
                json_out=json_out, exit_code=3,
            )
            return
    else:
        result = build_financial_register(project, now_utc=now_utc, since_utc=since_utc)
        result["written_paths"] = []

    payload = {
        "command": "hb-assistant procore obsidian financial", "ok": True,
        "phase": _FINANCIAL_PHASE, "project_key": project,
        "mode": "apply" if apply else "dry_run", "dry_run": not apply,
        "since_utc": since_utc, "generated_utc": now_utc, "counts": result["counts"],
        "section_keys": list(result["sections"]), "rendered": result["rendered"],
        "written_paths": result["written_paths"], "guardrails": result["guardrails"],
    }
    _emit(payload, json_out=json_out)


# =============================================================================
# Prompt_09A: procore obsidian register (endpoint-scoped projection from
# Phase 04A procore_live_records; read-only SQLite, never calls Procore)
# =============================================================================

@obsidian_app.command("register")
def obsidian_register(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key (per procore_projects.seed.yaml)."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id (e.g. rfis, submittals, observations, meetings, daily-log-weather)."),
    from_sqlite: bool = typer.Option(False, "--from-sqlite", help="REQUIRED. Asserts the read source is the local SQLite procore_live_records table (no live Procore call)."),
    dry_run: bool = typer.Option(True, "--dry-run", help="Default: rendered Markdown preview + counts, zero side effects."),
    apply: bool = typer.Option(False, "--apply", help="EXPLICIT opt-in. Writes the marker-bounded register section into 01_Projects/<project>.procore-<family>-register.md."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Structured JSON envelope (default). Use --no-json for compact human-readable form."),
    confirm: bool = typer.Option(False, "--confirm", help="Required with --apply in non-TTY contexts."),
) -> None:
    """Project Phase 04A procore_live_records into a per-family Obsidian register section.

    Read-only over local SQLite — never calls Procore. Supported endpoints map
    to one of: rfi_register, submittal_register, observation_register,
    meeting_register, daily_log_index. Unsupported endpoints (projects,
    punch-items, schedules, activities) are rejected with a structured error
    pointing at the operator runbook.
    """
    if not from_sqlite:
        payload = {
            "command": "hb-assistant procore obsidian register",
            "ok": False,
            "phase": "Phase 04A Prompt 09A",
            "project_key": project,
            "endpoint_id": endpoint,
            "status": "missing_required_flag",
            "error": "--from-sqlite is required (asserts no live Procore call).",
            "guardrails": _GUARDRAILS,
        }
        _emit(payload, json_out=json_out, exit_code=2)
        return

    if apply and not confirm and not sys.stdin.isatty():
        typer.echo("ERROR: --confirm required for non-TTY --apply (guardrail).", err=True)
        raise typer.Exit(1)
    if apply and not confirm and not typer.confirm(
        "CONFIRM: --apply will write a marker-bounded register section to the local vault only (no Procore mutation). Continue?",
        default=False,
    ):
        typer.echo("Aborted.")
        raise typer.Exit(1)

    from hb_assistant.procore import endpoints as ep_registry
    from hb_assistant.procore.obsidian import procore_obsidian_register

    adapter = ep_registry.get(endpoint)
    if adapter is None:
        payload = {
            "command": "hb-assistant procore obsidian register",
            "ok": False,
            "phase": "Phase 04A Prompt 09A",
            "project_key": project,
            "endpoint_id": None,
            "command_endpoint": endpoint,
            "status": "endpoint_alias_unknown",
            "reason_codes": ["endpoint_alias_unknown"],
            "guardrails": _GUARDRAILS,
        }
        _emit(payload, json_out=json_out, exit_code=2)
        return

    result = procore_obsidian_register(
        project_key=project,
        endpoint_id=adapter.endpoint_id,
        dry_run=dry_run and not apply,
        apply=apply,
        json_out=json_out,
    )

    envelope: dict[str, Any] = {
        "command": "hb-assistant procore obsidian register",
        "phase": "Phase 04A Prompt 09A",
        "command_endpoint": endpoint,
        "legacy_endpoint_alias": adapter.legacy_endpoint_alias,
        **result,
    }
    if envelope.get("status") == "unsupported_endpoint":
        _emit(envelope, json_out=json_out, exit_code=2)
        return
    if not envelope.get("ok", False):
        _emit(envelope, json_out=json_out, exit_code=3)
        return
    _emit(envelope, json_out=json_out)


# =============================================================================
# Prompt_11: procore validate (read-only operator stack-readiness check)
# =============================================================================


@app.command("validate")
def validate_cmd(
    json_out: bool = typer.Option(True, "--json/--no-json", help="Structured JSON envelope (default)."),
    strict: bool = typer.Option(
        False,
        "--strict",
        help=(
            "Tighten pass criteria: env_absent/env_partial auth and missing "
            "procore_* tables become hard failures. Never enables any I/O."
        ),
    ),
) -> None:
    """Read-only Procore stack-readiness check.

    Cross-checks seed configs, mapping, redaction module, Obsidian renderer
    + templates, vault writer posture, schema migrator state, and auth
    credential presence — entirely local, no live Procore call, no write.
    Exit 0 when every check passes, 1 otherwise.
    """

    from hb_assistant.procore.validate import run_procore_validate  # lazy import

    envelope = run_procore_validate(strict=strict)

    if json_out:
        typer.echo(json.dumps(envelope, indent=2, default=str))
    else:
        for check in envelope["checks"]:
            mark = "ok" if check.get("ok") else "FAIL"
            typer.echo(f"[{mark}] {check['name']}")
        typer.echo(
            f"overall: {'ok' if envelope['ok'] else 'FAIL'} "
            f"({envelope['summary']['passed']}/{envelope['summary']['total']} passed)"
        )

    raise typer.Exit(0 if envelope["ok"] else 1)
