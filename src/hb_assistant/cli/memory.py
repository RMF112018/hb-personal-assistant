"""`hb-assistant memory` — opt-in, bounded, source-backed memory compiler (N8C-7).

Compiles entities/concepts/topics from a context pack's source-backed items into advisory memory
nodes/mentions/compilations. There is no background compiler and no backend/scheduler auto-start.
``preview`` and ``compile --dry-run`` are fully read-only; only ``compile --apply`` persists, and only
into the four memory-owned tables. Compilation is pack-scoped (``--pack-id``); there is no global
compile-all default.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded source-backed memory compiler (never auto-started).")


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
    from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
    from hb_assistant.obsidian_mcp.memory_compiler import MemoryProviders
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    return MemoryProviders(ClaimRepository(db), ContextPackRepository(db), EnrichmentRepository(db),
                           SourceIndexRepository(db))


@app.command("preview")
def preview(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to compile memory from."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Discover + compile memory candidates from a pack WITHOUT persisting (read-only)."""
    from hb_assistant.obsidian_mcp import memory_compiler as mc

    _emit(mc.preview_memory_compilation(_providers(_db_path(db)), pack_id=pack_id, created_by="cli"),
          json_out=json_out)


@app.command("compile")
def compile_(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to compile memory from."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Compile memory for a pack; only ``--apply`` persists (memory-owned tables only)."""
    from hb_assistant.obsidian_mcp import memory_compiler as mc
    from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository

    db_path = _db_path(db)
    result = mc.apply_memory_compilation(_providers(db_path), MemoryRepository(db_path),
                                         pack_id=pack_id, apply=not dry_run, created_by="cli")
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("export")
def export(
    node_id: str = typer.Option(..., "--node-id"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted memory node (read-only)."""
    from hb_assistant.obsidian_mcp import memory_compiler as mc
    from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository

    repo = MemoryRepository(_db_path(db))
    node = repo.get_node(node_id)
    if node is None:
        _emit({"error": "memory_node_not_found", "node_id": node_id}, json_out=json_out, exit_code=1)
    _emit(mc.export_memory_node(node, repo.list_mentions(node_id), repo.list_compilations(node_id)),
          json_out=json_out)


@app.command("list")
def list_nodes(
    node_type: Optional[str] = typer.Option(None, "--node-type"),
    status: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted memory nodes."""
    from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository

    nodes = MemoryRepository(_db_path(db)).list_nodes(node_type=node_type, status=status, limit=limit)
    _emit({"memory_nodes": nodes, "count": len(nodes)}, json_out=json_out)
