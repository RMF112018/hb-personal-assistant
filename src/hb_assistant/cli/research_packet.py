"""`hb-assistant research-packet` — opt-in, bounded, review-aware answer-context packets (N8C-11).

Materializes bounded, citation-backed research packets + answer-context contracts from the N8C-10
intelligence projections. There is no background packet builder and no backend/scheduler auto-start. It
generates NO final answer — the answer contract is guidance metadata only.

``preview`` / ``list`` / ``export`` and ``build --dry-run`` are fully read-only. Only ``build --apply``
persists, and only into the five N8C-11 packet tables. Packets are read PRODUCTS — building one never
mutates a source, review, or projection record, never converts a candidate into accepted truth, and executes
nothing.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded review-aware answer-context packets (never auto-started).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _providers(db: str) -> Any:
    from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
        IntelligenceProjectionRepository,
    )
    from hb_assistant.obsidian_mcp.research_packet_builder import PacketProviders

    return PacketProviders(IntelligenceProjectionRepository(db))


@app.command("preview")
def preview(
    projection_id: str = typer.Option(..., "--projection-id", help="N8C-10 projection to build from."),
    packet_type: str = typer.Option("review_aware_answer_context", "--type",
        help="trusted_answer_context | review_aware_answer_context | implementation_research_context | ..."),
    objective: Optional[str] = typer.Option(None, "--objective"),
    question: Optional[str] = typer.Option(None, "--question"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a review-aware answer-context packet from a projection WITHOUT persisting (read-only)."""
    from hb_assistant.obsidian_mcp import research_packet_builder as pb
    from hb_assistant.obsidian_mcp.research_packet_models import ResearchPacketValidationError

    try:
        _emit(pb.preview_research_packet(_providers(_db_path(db)), projection_id=projection_id,
                                         packet_type=packet_type, objective=objective, question=question,
                                         created_by="cli", limit=limit), json_out=json_out)
    except ResearchPacketValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)


@app.command("build")
def build(
    projection_id: str = typer.Option(..., "--projection-id", help="N8C-10 projection to build from."),
    packet_type: str = typer.Option("review_aware_answer_context", "--type"),
    objective: Optional[str] = typer.Option(None, "--objective"),
    question: Optional[str] = typer.Option(None, "--question"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build an answer-context packet; only ``--apply`` persists (packet tables only)."""
    from hb_assistant.obsidian_mcp import research_packet_builder as pb
    from hb_assistant.obsidian_mcp.research_packet_models import ResearchPacketValidationError
    from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository

    db_path = _db_path(db)
    try:
        result = pb.build_research_packet(
            _providers(db_path), ResearchPacketRepository(db_path), projection_id=projection_id,
            packet_type=packet_type, objective=objective, question=question, apply=not dry_run,
            created_by="cli", limit=limit)
    except ResearchPacketValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("list")
def list_packets(
    packet_type: Optional[str] = typer.Option(None, "--type"),
    status: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted research packets."""
    from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository

    repo = ResearchPacketRepository(_db_path(db))
    packets = repo.list_research_packets(packet_type=packet_type, status=status, limit=limit)
    _emit({"packets": packets, "count": len(packets)}, json_out=json_out)


@app.command("export")
def export(
    packet_id: str = typer.Option(..., "--packet-id"),
    included_only: bool = typer.Option(True, "--included-only/--all-items"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted packet (read-only; header + answer contract + bounded items +
    bounded citations). No answer prose, no full payloads, no Markdown/HTML/PDF writer."""
    from hb_assistant.obsidian_mcp import research_packet_builder as pb
    from hb_assistant.obsidian_mcp.research_packet_models import ResearchPacketValidationError
    from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository

    try:
        _emit(pb.export_research_packet(ResearchPacketRepository(_db_path(db)), packet_id=packet_id,
                                        included_only=included_only, limit=limit), json_out=json_out)
    except ResearchPacketValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
