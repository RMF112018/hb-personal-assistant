"""construction-agent CLI subcommands.

Commands:
- ``hb-assistant construction-agent sources validate [--json]`` — load and
  validate the seeded source registry (Phase 01 Step 2).
- ``hb-assistant construction-agent graph auth status [--json]`` — report
  delegated MSAL cache status (Phase 01 Step 4).
- ``hb-assistant construction-agent graph sources resolve [--source KEY]
  [--apply] [--json]`` — resolve SharePoint/OneDrive sources to canonical
  Graph IDs (Phase 01 Step 4).
- ``hb-assistant construction-agent graph delta --source KEY [--dry-run |
  --apply] [--max-pages N] [--json]`` — read-only Graph delta crawler
  (Phase 01 Step 4).

All commands are read-only against external systems; only SQLite metadata is
written, and only when ``--apply`` is set.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer
from pydantic import ValidationError

from hb_assistant.auth.providers import DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.config import (
    SourceRegistry,
    load_source_registry,
)
from hb_assistant.construction.config.loader import SourceRegistryError
from hb_assistant.construction.graph import (
    GRAPH_SCOPES,
    ConstructionDeltaCrawler,
    ConstructionGraphResolver,
    ResolutionResult,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpClient

app = typer.Typer(help="Construction-management intelligence layer (read-only).")
sources_app = typer.Typer(help="Source registry inspection.")
graph_app = typer.Typer(help="Read-only Microsoft Graph crawler.")
graph_sources_app = typer.Typer(help="Graph source resolution.")
app.add_typer(sources_app, name="sources")
app.add_typer(graph_app, name="graph")
graph_app.add_typer(graph_sources_app, name="sources")


def _build_report(registry: SourceRegistry) -> dict[str, Any]:
    resolved = [s for s in registry.sources if s.resolution_status == "resolved"]
    pending = [s for s in registry.sources if s.resolution_status == "pending"]
    deprecated = [s for s in registry.sources if s.resolution_status == "deprecated"]

    warnings: list[str] = []
    if pending:
        warnings.append(f"{len(pending)} sources pending live resolution")
    if deprecated:
        warnings.append(f"{len(deprecated)} sources marked deprecated")

    all_read_only = all(s.read_only is True for s in registry.sources)

    return {
        "implemented": True,
        "phase": 1,
        "step": "2-source-registry",
        "summary": {
            "project_count": len(registry.projects),
            "source_count": len(registry.sources),
            "resolved_count": len(resolved),
            "pending_count": len(pending),
            "deprecated_count": len(deprecated),
            "ok": True,
            "blocking": False,
        },
        "projects": [p.model_dump() for p in registry.projects],
        "sources": [s.model_dump() for s in registry.sources],
        "warnings": warnings,
        "guardrails": {
            "all_read_only": all_read_only,
            "no_writeback_paths": True,
            "no_live_external_calls": True,
        },
        "note": "Read-only validation. No SharePoint/OneDrive/Graph calls were made.",
    }


@sources_app.command("validate")
def validate_sources(
    json_out: bool = typer.Option(True, "--json", help="Emit structured JSON (default)."),
) -> None:
    """Validate the construction-agent source registry and emit a report."""

    try:
        registry = load_source_registry()
    except SourceRegistryError as e:
        payload = {
            "implemented": True,
            "phase": 1,
            "step": "2-source-registry",
            "summary": {"ok": False, "blocking": True},
            "error": "source_registry_unavailable",
            "detail": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
    except ValidationError as e:
        payload = {
            "implemented": True,
            "phase": 1,
            "step": "2-source-registry",
            "summary": {"ok": False, "blocking": True},
            "error": "schema_validation_failed",
            "detail": e.errors(),
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None

    report = _build_report(registry)
    typer.echo(json.dumps(report, indent=2) if json_out else str(report))
    raise typer.Exit(0)


def _build_auth_provider() -> DelegatedAuthProvider:
    cfg = load_config()
    pp = PathPolicy(cfg)
    return DelegatedAuthProvider(
        cfg.identity.tenant_id,
        cfg.identity.client_id,
        cfg.identity.delegated_scopes,
        path_policy=pp,
    )


def _build_graph_client_or_auth_payload(
    provider: DelegatedAuthProvider,
) -> tuple[Optional[GraphHttpClient], Optional[dict[str, Any]]]:
    """Return (client, auth_required_payload).

    The CLI never triggers an interactive login. If no cached token exists
    for the required scopes, we return a structured ``auth_required`` payload
    so non-interactive callers (CI, sandboxes) can interpret the result.
    """

    try:
        token = provider.get_token(GRAPH_SCOPES)
    except Exception as e:  # noqa: BLE001 — surface as structured payload
        return None, {
            "status": "auth_required",
            "scopes": GRAPH_SCOPES,
            "detail": str(e)[:200],
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }

    if "access_token" not in token:
        return None, {
            "status": "auth_required",
            "scopes": GRAPH_SCOPES,
            "detail": token.get("error_description") or token.get("error") or "no_access_token_in_cache",
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }

    def token_getter(scopes: Optional[list[str]] = None) -> dict[str, Any]:
        return provider.get_token(scopes or GRAPH_SCOPES)

    return GraphHttpClient(token_getter), None


@graph_app.command("auth")
def graph_auth_status(
    status: str = typer.Argument("status", help="Subcommand (only 'status' supported)."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report delegated MSAL cache status for the construction-agent scopes."""
    if status != "status":
        payload = {"status": "runtime_error", "error": f"unknown subcommand {status!r}"}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    provider = _build_auth_provider()
    info = provider.status_info()
    payload = {
        "command": "construction-agent graph auth status",
        "required_scopes": GRAPH_SCOPES,
        "delegated": info,
        "note": "No live Graph call is made; report is from local MSAL cache only.",
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


def _resolution_to_dict(r: ResolutionResult) -> dict[str, Any]:
    return r.model_dump()


@graph_sources_app.command("resolve")
def graph_sources_resolve(
    source: Optional[str] = typer.Option(
        None, "--source", help="Resolve only this source_key (default: all)."
    ),
    apply: bool = typer.Option(False, "--apply", help="Persist resolutions to SQLite."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Resolve registered SharePoint/OneDrive sources to canonical Graph IDs."""
    registry = load_source_registry()
    targets = [s for s in registry.sources if source is None or s.source_key == source]
    if not targets:
        payload = {
            "command": "construction-agent graph sources resolve",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    provider = _build_auth_provider()
    client, auth_payload = _build_graph_client_or_auth_payload(provider)
    if client is None:
        payload = {
            "command": "construction-agent graph sources resolve",
            "mode": "apply" if apply else "dry_run",
            "targets": [s.source_key for s in targets],
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    store = ConstructionStore() if apply else None
    resolver = ConstructionGraphResolver(client, store=store)
    results = [resolver.resolve(s, apply=apply) for s in targets]

    payload = {
        "command": "construction-agent graph sources resolve",
        "mode": "apply" if apply else "dry_run",
        "results": [_resolution_to_dict(r) for r in results],
        "summary": {
            "total": len(results),
            "resolved": sum(1 for r in results if r.status == "resolved"),
            "pending": sum(1 for r in results if r.status == "pending"),
            "unsupported": sum(1 for r in results if r.status == "unsupported"),
            "error": sum(1 for r in results if r.status == "error"),
        },
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "metadata_only": True,
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@graph_app.command("delta")
def graph_delta(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run; --apply persists."),
    max_pages: int = typer.Option(50, "--max-pages", help="Hard cap on pages per call."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Run the read-only Graph delta crawler for a single registered source."""
    registry = load_source_registry()
    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "construction-agent graph delta",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    provider = _build_auth_provider()
    client, auth_payload = _build_graph_client_or_auth_payload(provider)
    if client is None:
        payload = {
            "command": "construction-agent graph delta",
            "source": source,
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    store = ConstructionStore()
    crawler = ConstructionDeltaCrawler(client, store=store)
    receipt = crawler.crawl(source_key=source, dry_run=dry_run, max_pages=max_pages)

    payload = {
        "command": "construction-agent graph delta",
        "source": source,
        "mode": receipt.mode,
        "status": receipt.status,
        "receipt": receipt.model_dump(),
        "guardrails": {
            "external_systems": "read_only",
            "metadata_only": True,
            "delta_token_storage": "sqlite",
            "no_writeback": True,
        },
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if receipt.status in {"ok", "unresolved"} else 1)
