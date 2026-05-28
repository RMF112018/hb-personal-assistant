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
    ProcoreProjectsError,
    check_auth_status,
    load_endpoint_contract,
    load_procore_projects,
)
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
    """Report Procore auth-credential presence (no live call)."""

    report = check_auth_status()
    payload = {
        "command": "hb-assistant procore auth status",
        "report": report.model_dump(),
        "guardrails": _GUARDRAILS,
    }
    _emit(payload, json_out=json_out)


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

@sync_app.command("run")
def sync_run(
    project: Optional[str] = typer.Option(None, "--project", help="HB pilot key or mapped project (pending keys allowed for planning)"),
    dry_run: bool = typer.Option(True, "--dry-run", help="Default: plan only, redacted, zero side effects"),
    apply: bool = typer.Option(False, "--apply", help="EXPLICIT opt-in only. Writes local SQLite normalized rows after audit gate. Never external."),
    full_refresh: bool = typer.Option(False, "--full-refresh"),
    json_out: bool = typer.Option(True, "--json"),
    confirm: bool = typer.Option(False, "--confirm", help="Required with --apply in non-TTY contexts"),
) -> None:
    """Dry-run (default) or apply (opt-in) for pilot projects.

    Audit prerequisite (Prompt_07 surfaces) is mandatory before any planning or execution.
    All writes are local SQLite only (temp DB supported for validation). GET-only. Redacted.
    """
    if apply and not confirm and not sys.stdin.isatty():
        typer.echo("ERROR: --confirm required for non-TTY --apply (guardrail).", err=True)
        raise typer.Exit(1)

    if apply and not confirm and not typer.confirm("CONFIRM: --apply will write to local SQLite only (no Procore mutation). Continue?", default=False):
        typer.echo("Aborted.")
        raise typer.Exit(1)

    from hb_assistant.procore.sync import run_sync  # lazy, after guard checks

    result = run_sync(
        project_key=project,
        dry_run=dry_run and not apply,
        apply=apply,
        full_refresh=full_refresh,
        json_output=json_out,
    )
    _emit(result, json_out=json_out)


# Register the new sub-app (additive; existing surfaces untouched)
app.add_typer(sync_app, name="sync", help="Pilot project dry-run sync (Prompt_09) — audit-gated, local SQLite only")

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
