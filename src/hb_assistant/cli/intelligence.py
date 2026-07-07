"""`hb-assistant intelligence` — opt-in, bounded, review-aware intelligence projections (N8C-10).

Materializes bounded, effective-state-filtered context projections (trusted / candidate / review-aware /
implementation) from the advisory records + the N8C-9 review overlay. There is no background projection
builder and no backend/scheduler auto-start.

``preview`` / ``list`` / ``export`` and ``build --dry-run`` are fully read-only. Only ``build --apply``
persists, and only into the four N8C-10 projection tables. Projections are read PRODUCTS — building one
never mutates a source or review record, never converts a candidate into accepted truth, and executes
nothing.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded review-aware intelligence projections (never auto-started).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _providers(db: str) -> Any:
    from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
    from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
    from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
    from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
    from hb_assistant.obsidian_mcp.intelligence_projection_builder import ProjectionProviders
    from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
    from hb_assistant.obsidian_mcp.review_builder import ReviewProviders
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    review_providers = ReviewProviders(ContextPackRepository(db), ClaimRepository(db),
                                       EnrichmentRepository(db), SourceIndexRepository(db),
                                       MemoryRepository(db), DecisionMemoryRepository(db))
    return ProjectionProviders(review_providers, ReviewRepository(db))


def _kinds(kind: Optional[str]) -> tuple[str, ...]:
    from hb_assistant.obsidian_mcp.review_builder import ALL_KINDS
    if not kind:
        return ALL_KINDS
    return tuple(k.strip() for k in kind.split(",") if k.strip())


@app.command("preview")
def preview(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to project from."),
    projection_type: str = typer.Option("review_aware_context", "--type",
        help="trusted_context | candidate_context | review_aware_context | implementation_context | ..."),
    kind: Optional[str] = typer.Option(None, "--kind", help="Comma-separated families. Default = all."),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a review-aware projection for a pack WITHOUT persisting (read-only)."""
    from hb_assistant.obsidian_mcp import intelligence_projection_builder as ib
    from hb_assistant.obsidian_mcp.intelligence_projection_models import ProjectionValidationError

    try:
        _emit(ib.preview_intelligence_projection(_providers(_db_path(db)), pack_id=pack_id,
                                                 projection_type=projection_type, kinds=_kinds(kind),
                                                 created_by="cli", limit=limit), json_out=json_out)
    except ProjectionValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)


@app.command("build")
def build(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to project from."),
    projection_type: str = typer.Option("review_aware_context", "--type"),
    kind: Optional[str] = typer.Option(None, "--kind", help="Comma-separated families. Default = all."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a projection for a pack; only ``--apply`` persists (projection tables only)."""
    from hb_assistant.obsidian_mcp import intelligence_projection_builder as ib
    from hb_assistant.obsidian_mcp.intelligence_projection_models import ProjectionValidationError
    from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
        IntelligenceProjectionRepository,
    )

    db_path = _db_path(db)
    try:
        result = ib.build_intelligence_projection(
            _providers(db_path), IntelligenceProjectionRepository(db_path), pack_id=pack_id,
            projection_type=projection_type, kinds=_kinds(kind), apply=not dry_run, created_by="cli",
            limit=limit)
    except ProjectionValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("list")
def list_projections(
    projection_type: Optional[str] = typer.Option(None, "--type"),
    status: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted projections."""
    from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
        IntelligenceProjectionRepository,
    )

    repo = IntelligenceProjectionRepository(_db_path(db))
    projections = repo.list_projections(projection_type=projection_type, status=status, limit=limit)
    _emit({"projections": projections, "count": len(projections)}, json_out=json_out)


@app.command("export")
def export(
    projection_id: str = typer.Option(..., "--projection-id"),
    included_only: bool = typer.Option(True, "--included-only/--all-items"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted projection (read-only; ids/digests/state + bounded excerpts)."""
    from hb_assistant.obsidian_mcp import intelligence_projection_builder as ib
    from hb_assistant.obsidian_mcp.intelligence_projection_models import ProjectionValidationError
    from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
        IntelligenceProjectionRepository,
    )

    try:
        _emit(ib.export_intelligence_projection(IntelligenceProjectionRepository(_db_path(db)),
                                               projection_id=projection_id, included_only=included_only,
                                               limit=limit), json_out=json_out)
    except ProjectionValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
