"""construction-agent CLI subcommands.

Phase 01 Step 2: read-only source registry inspection.

Commands:
- ``hb-assistant construction-agent sources validate [--json]`` — load and
  validate the seeded source registry, emit a structured report including
  per-source resolution status and guardrail attestations. Never contacts
  external systems.
"""

from __future__ import annotations

import json
from typing import Any

import typer
from pydantic import ValidationError

from hb_assistant.construction.config import (
    SourceRegistry,
    load_source_registry,
)
from hb_assistant.construction.config.loader import SourceRegistryError

app = typer.Typer(help="Construction-management intelligence layer (read-only).")
sources_app = typer.Typer(help="Source registry inspection.")
app.add_typer(sources_app, name="sources")


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
