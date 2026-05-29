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

import json
import sys
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
from hb_assistant.procore.errors import ProcoreAPIError
from hb_assistant.procore.models import EndpointAuditRunReceipt

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


@live_app.command("sync")
def live_sync(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id (e.g. rfis, submittals, projects, daily-log-weather)."),
    apply: bool = typer.Option(False, "--apply", help="Required for live intent."),
    sqlite_only: bool = typer.Option(True, "--sqlite-only", help="Required guardrail; no source-system mutation."),
    max_pages: int = typer.Option(3, "--max-pages", min=1),
    max_items: int = typer.Option(100, "--max-items", min=1),
    confirm_live_get: bool = typer.Option(False, "--confirm-live-get"),
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
        mode_hint="live_apply" if apply else "live_dry_run",
        evidence_path="docs/evidence/construction-intelligence-phase-04a/02-endpoint-command-matrix.md",
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


@live_app.command("smoke")
def live_smoke(
    project: str = typer.Option(..., "--project", help="Mapped pilot project key."),
    endpoint: str = typer.Option(..., "--endpoint", help="Canonical endpoint id."),
    max_pages: int = typer.Option(1, "--max-pages", min=1),
    max_items: int = typer.Option(10, "--max-items", min=1),
    confirm_live_get: bool = typer.Option(False, "--confirm-live-get"),
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


live_records_app = typer.Typer(help="Procore live SQLite record read-only commands.")
live_app.add_typer(live_records_app, name="records")


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
