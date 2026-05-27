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
from typing import Any

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

app = typer.Typer(help="Procore foundation: read-only endpoint audit (dry-run only).")
auth_app = typer.Typer(help="Procore auth status (no live call).")
tools_app = typer.Typer(help="Procore endpoint catalog + dry-run audit.")
mapping_app = typer.Typer(help="Procore project mapping validation.")
projects_app = typer.Typer(help="Procore projects registry (read-only).")
companies_app = typer.Typer(help="Procore company context (read-only).")
app.add_typer(auth_app, name="auth")
app.add_typer(tools_app, name="tools")
app.add_typer(mapping_app, name="mapping")
app.add_typer(projects_app, name="projects")
app.add_typer(companies_app, name="companies")


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
