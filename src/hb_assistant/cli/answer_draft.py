"""`hb-assistant answer-draft` — opt-in, bounded, citation-safe answer DRAFTS (N8C-14).

Materializes bounded, citation-backed DRAFT answer artifacts from the N8C-11 research packets: cited sections
that preserve review labels, source provenance, excluded-content rules, and the packet's no-execution policy.
There is no background draft builder and no backend/scheduler auto-start. It generates NO final/authoritative
answer — a draft is guidance, never operator-approved truth, and nothing is executed.

``preview`` / ``list`` / ``export`` and ``build --dry-run`` are fully read-only. Only ``build --apply``
persists, and only into the five N8C-14 draft tables. Drafts are read PRODUCTS — building one never mutates a
packet, projection, review, or source record, never converts a candidate into accepted truth, and never
performs a live source file read (source metadata is read from the index only).
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded citation-safe answer drafts (never auto-started).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _providers(db: str) -> Any:
    from hb_assistant.obsidian_mcp.answer_draft_builder import DraftProviders
    from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    return DraftProviders(packet_repo=ResearchPacketRepository(db), source_repo=SourceIndexRepository(db))


@app.command("preview")
def preview(
    packet_id: str = typer.Option(..., "--packet-id", help="N8C-11 research packet to draft from."),
    draft_type: str = typer.Option("review_aware_answer_draft", "--type",
        help="trusted_answer_draft | review_aware_answer_draft | implementation_context_draft | ..."),
    objective: Optional[str] = typer.Option(None, "--objective"),
    question: Optional[str] = typer.Option(None, "--question"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a citation-safe answer draft from a packet WITHOUT persisting (read-only)."""
    from hb_assistant.obsidian_mcp import answer_draft_builder as ab
    from hb_assistant.obsidian_mcp.answer_draft_models import AnswerDraftValidationError

    try:
        _emit(ab.preview_answer_draft(_providers(_db_path(db)), packet_id=packet_id, draft_type=draft_type,
                                      objective=objective, question=question, created_by="cli", limit=limit),
              json_out=json_out)
    except AnswerDraftValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)


@app.command("build")
def build(
    packet_id: str = typer.Option(..., "--packet-id", help="N8C-11 research packet to draft from."),
    draft_type: str = typer.Option("review_aware_answer_draft", "--type"),
    objective: Optional[str] = typer.Option(None, "--objective"),
    question: Optional[str] = typer.Option(None, "--question"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a citation-safe answer draft; only ``--apply`` persists (draft tables only)."""
    from hb_assistant.obsidian_mcp import answer_draft_builder as ab
    from hb_assistant.obsidian_mcp.answer_draft_models import AnswerDraftValidationError
    from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository

    db_path = _db_path(db)
    try:
        result = ab.build_answer_draft(
            _providers(db_path), AnswerDraftRepository(db_path), packet_id=packet_id, draft_type=draft_type,
            objective=objective, question=question, apply=not dry_run, created_by="cli", limit=limit)
    except AnswerDraftValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("list")
def list_drafts(
    draft_type: Optional[str] = typer.Option(None, "--type"),
    status: Optional[str] = typer.Option(None, "--status"),
    packet_id: Optional[str] = typer.Option(None, "--packet-id"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted answer drafts."""
    from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository

    repo = AnswerDraftRepository(_db_path(db))
    drafts = repo.list_answer_drafts(draft_type=draft_type, status=status, packet_id=packet_id, limit=limit)
    _emit({"drafts": drafts, "count": len(drafts)}, json_out=json_out)


@app.command("export")
def export(
    draft_id: str = typer.Option(..., "--draft-id"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted draft (read-only; header + bounded sections + bounded citations).
    No final answer, no answer prose, no full payloads, no Markdown/HTML/PDF writer."""
    from hb_assistant.obsidian_mcp import answer_draft_builder as ab
    from hb_assistant.obsidian_mcp.answer_draft_models import AnswerDraftValidationError
    from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository

    try:
        _emit(ab.export_answer_draft(AnswerDraftRepository(_db_path(db)), draft_id=draft_id, limit=limit),
              json_out=json_out)
    except AnswerDraftValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
