"""`hb-assistant decision-memory` — opt-in, bounded, source-backed decision/preference/open-loop
extractor (N8C-8).

Turns a context pack's claims (and the pack's memory compilations) into advisory decision / preference /
open-loop records. There is no background extractor and no backend/scheduler auto-start. ``preview`` and
``extract --dry-run`` are fully read-only; only ``extract --apply`` persists, and only into the four
N8C-8-owned tables. Extraction is pack-scoped (``--pack-id``); nothing is executed, scheduled, or sent.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded decision/preference/open-loop extractor (never auto-started).")


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
    from hb_assistant.obsidian_mcp.decision_memory_extractor import DecisionMemoryProviders
    from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
    from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    return DecisionMemoryProviders(ClaimRepository(db), ContextPackRepository(db),
                                   EnrichmentRepository(db), SourceIndexRepository(db),
                                   MemoryRepository(db))


@app.command("preview")
def preview(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to extract records from."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Discover + build decision/preference/open-loop records from a pack WITHOUT persisting (read-only)."""
    from hb_assistant.obsidian_mcp import decision_memory_extractor as ex

    _emit(ex.preview_decision_memory(_providers(_db_path(db)), pack_id=pack_id, created_by="cli"),
          json_out=json_out)


@app.command("extract")
def extract(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to extract records from."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Extract records for a pack; only ``--apply`` persists (N8C-8-owned tables only)."""
    from hb_assistant.obsidian_mcp import decision_memory_extractor as ex
    from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository

    db_path = _db_path(db)
    result = ex.apply_decision_memory(_providers(db_path), DecisionMemoryRepository(db_path),
                                      pack_id=pack_id, apply=not dry_run, created_by="cli")
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("export")
def export(
    kind: str = typer.Option(..., "--kind", help="decisions | preferences | open-loops"),
    status: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of persisted records (read-only)."""
    from hb_assistant.obsidian_mcp import decision_memory_extractor as ex
    from hb_assistant.obsidian_mcp.decision_memory_models import DecisionMemoryValidationError
    from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository

    try:
        _emit(ex.export_decision_memory(DecisionMemoryRepository(_db_path(db)), kind=kind,
                                        status=status, limit=limit), json_out=json_out)
    except DecisionMemoryValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)


@app.command("list")
def list_records(
    kind: str = typer.Option(..., "--kind", help="decisions | preferences | open-loops"),
    status: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted records for one kind."""
    from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository

    repo = DecisionMemoryRepository(_db_path(db))
    if kind == "decisions":
        records = repo.list_decisions(status=status, limit=limit)
    elif kind == "preferences":
        records = repo.list_preferences(status=status, limit=limit)
    elif kind == "open-loops":
        records = repo.list_open_loops(status=status, limit=limit)
    else:
        _emit({"error": f"unknown_kind:{kind}"}, json_out=json_out, exit_code=1)
    _emit({"kind": kind, "records": records, "count": len(records)}, json_out=json_out)
