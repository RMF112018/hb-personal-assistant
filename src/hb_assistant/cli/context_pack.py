"""`hb-assistant context-pack` — opt-in, bounded context-pack builder (N8C-6).

Assembles reviewable, source-linked intelligence packets from the N8C substrate. There is no
background builder and no backend/scheduler auto-start. ``preview`` and ``build --dry-run`` are fully
read-only; only ``build --apply`` persists, and only into the four context-pack-owned tables.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded context-pack builder (never auto-started).")


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
    from hb_assistant.obsidian_mcp.context_pack_builder import Providers
    from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    return Providers(EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db))


def _request(*, pack_type: str, source_ids: Optional[str], job_type: Optional[str],
             review_tier: Optional[str], max_items: int, max_chars: int, max_chars_per_item: int,
             content_level: str, title: Optional[str], objective: Optional[str]) -> Any:
    from hb_assistant.obsidian_mcp.context_pack_builder import PackRequest
    from hb_assistant.obsidian_mcp.context_pack_models import Budget

    scope: dict[str, Any] = {}
    ids = [s.strip() for s in (source_ids or "").split(",") if s.strip()]
    if ids:
        scope["source_ids"] = ids
    if job_type:
        scope["job_type"] = job_type
    if review_tier:
        scope["review_tier"] = review_tier
    budget = Budget(max_items=max_items, max_chars=max_chars, max_chars_per_item=max_chars_per_item,
                    include_content_level=content_level)
    return PackRequest(pack_type=pack_type, scope=scope, budget=budget, title=title,
                       objective=objective, created_by="cli")


@app.command("preview")
def preview(
    pack_type: str = typer.Option("enrichment_review", "--pack-type"),
    source_ids: Optional[str] = typer.Option(None, "--source-ids", help="Comma-separated source anchors."),
    job_type: Optional[str] = typer.Option(None, "--job-type"),
    review_tier: Optional[str] = typer.Option(None, "--review-tier"),
    max_items: int = typer.Option(50, "--max-items"),
    max_chars: int = typer.Option(60000, "--max-chars"),
    max_chars_per_item: int = typer.Option(4000, "--max-chars-per-item"),
    content_level: str = typer.Option("deep_bounded", "--content-level"),
    title: Optional[str] = typer.Option(None, "--title"),
    objective: Optional[str] = typer.Option(None, "--objective"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Assemble a pack WITHOUT persisting (read-only)."""
    from hb_assistant.obsidian_mcp import context_pack_builder as builder

    path = _db_path(db)
    req = _request(pack_type=pack_type, source_ids=source_ids, job_type=job_type,
                   review_tier=review_tier, max_items=max_items, max_chars=max_chars,
                   max_chars_per_item=max_chars_per_item, content_level=content_level,
                   title=title, objective=objective)
    _emit(builder.preview_context_pack(req, _providers(path)), json_out=json_out)


@app.command("build")
def build(
    pack_type: str = typer.Option("enrichment_review", "--pack-type"),
    source_ids: Optional[str] = typer.Option(None, "--source-ids", help="Comma-separated source anchors."),
    job_type: Optional[str] = typer.Option(None, "--job-type"),
    review_tier: Optional[str] = typer.Option(None, "--review-tier"),
    max_items: int = typer.Option(50, "--max-items"),
    max_chars: int = typer.Option(60000, "--max-chars"),
    max_chars_per_item: int = typer.Option(4000, "--max-chars-per-item"),
    content_level: str = typer.Option("deep_bounded", "--content-level"),
    title: Optional[str] = typer.Option(None, "--title"),
    objective: Optional[str] = typer.Option(None, "--objective"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Assemble and (only with ``--apply``) persist a pack into the context-pack tables."""
    from hb_assistant.obsidian_mcp import context_pack_builder as builder
    from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository

    path = _db_path(db)
    req = _request(pack_type=pack_type, source_ids=source_ids, job_type=job_type,
                   review_tier=review_tier, max_items=max_items, max_chars=max_chars,
                   max_chars_per_item=max_chars_per_item, content_level=content_level,
                   title=title, objective=objective)
    result = builder.build_context_pack(req, _providers(path), ContextPackRepository(path),
                                        apply=not dry_run)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("export")
def export(
    pack_id: str = typer.Option(..., "--pack-id"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted pack (read-only)."""
    from hb_assistant.obsidian_mcp import context_pack_builder as builder
    from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository

    repo = ContextPackRepository(_db_path(db))
    pack = repo.get_pack(pack_id)
    if pack is None:
        _emit({"error": "context_pack_not_found", "pack_id": pack_id}, json_out=json_out, exit_code=1)
    _emit(builder.export_context_pack(pack, repo.list_items(pack_id)), json_out=json_out)


@app.command("list")
def list_packs(
    pack_type: Optional[str] = typer.Option(None, "--pack-type"),
    status: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted context packs."""
    from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository

    packs = ContextPackRepository(_db_path(db)).list_packs(pack_type=pack_type, status=status,
                                                           limit=limit)
    _emit({"context_packs": packs, "count": len(packs)}, json_out=json_out)
