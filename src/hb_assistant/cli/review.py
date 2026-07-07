"""`hb-assistant review` — opt-in, bounded, source-backed review queue + local disposition ledger (N8C-9).

Aggregates the advisory records from N8C-4…N8C-8 (claims, enrichment review, context-pack items, memory
compilations, decision/preference/open-loop records) into a unified, pack-scoped review queue, and records
explicit local/operator dispositions as an APPEND-ONLY ledger. There is no background review builder and no
backend/scheduler auto-start.

``preview`` / ``list`` / ``export`` and every ``--dry-run`` are fully read-only. Only ``build --apply``
(writes ``assistant_review_items``) and ``disposition --apply`` (appends to
``assistant_review_dispositions`` + ``assistant_review_events``) persist, and ONLY into the three
N8C-9-owned review tables. A disposition changes only the review-overlay effective state — nothing is
executed, scheduled, or sent.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded review queue + local disposition ledger (never auto-started).")

_DISPOSITIONS = {
    "accept": "accept", "reject": "reject", "defer": "defer",
    "not_required": "mark_not_required", "request_context": "request_more_context",
    "mark_stale": "mark_stale", "mark_superseded": "mark_superseded",
}


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
    from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
    from hb_assistant.obsidian_mcp.review_builder import ReviewProviders
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    return ReviewProviders(ContextPackRepository(db), ClaimRepository(db), EnrichmentRepository(db),
                           SourceIndexRepository(db), MemoryRepository(db),
                           DecisionMemoryRepository(db))


def _kinds(kind: Optional[str]) -> tuple[str, ...]:
    from hb_assistant.obsidian_mcp.review_builder import ALL_KINDS
    if not kind:
        return ALL_KINDS
    return tuple(k.strip() for k in kind.split(",") if k.strip())


@app.command("preview")
def preview(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to build the review queue from."),
    kind: Optional[str] = typer.Option(None, "--kind",
        help="Comma-separated families: claims,context-packs,enrichment,memory,decisions,"
             "preferences,open-loops. Default = all."),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Discover + build review items from a pack WITHOUT persisting (read-only)."""
    from hb_assistant.obsidian_mcp import review_builder as rb

    _emit(rb.preview_review_queue(_providers(_db_path(db)), pack_id=pack_id, kinds=_kinds(kind),
                                  created_by="cli", limit=limit), json_out=json_out)


@app.command("build")
def build(
    pack_id: str = typer.Option(..., "--pack-id", help="Context pack to build the review queue from."),
    kind: Optional[str] = typer.Option(None, "--kind", help="Comma-separated families. Default = all."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build review items for a pack; only ``--apply`` persists (``assistant_review_items`` only)."""
    from hb_assistant.obsidian_mcp import review_builder as rb
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository

    db_path = _db_path(db)
    result = rb.build_review_queue(_providers(db_path), ReviewRepository(db_path), pack_id=pack_id,
                                   kinds=_kinds(kind), apply=not dry_run, created_by="cli", limit=limit)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("list")
def list_items(
    state: Optional[str] = typer.Option(None, "--state", help="Filter by built review_state."),
    review_type: Optional[str] = typer.Option(None, "--type", help="Filter by review_type."),
    effective_state: Optional[str] = typer.Option(None, "--effective-state"),
    include_superseded: bool = typer.Option(False, "--include-superseded"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted review items."""
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository

    repo = ReviewRepository(_db_path(db))
    items = repo.list_review_items(review_state=state, review_type=review_type,
                                   effective_state=effective_state,
                                   include_superseded=include_superseded, limit=limit)
    _emit({"items": items, "count": len(items)}, json_out=json_out)


@app.command("effective-state")
def effective_state(
    item_id: str = typer.Option(..., "--item-id"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only effective state (built default, or latest disposition) for one review item."""
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository

    state = ReviewRepository(_db_path(db)).get_effective_state(item_id)
    if state is None:
        _emit({"error": f"review_item_not_found:{item_id}"}, json_out=json_out, exit_code=1)
    _emit(state, json_out=json_out)


@app.command("export")
def export(
    state: Optional[str] = typer.Option(None, "--state"),
    review_type: Optional[str] = typer.Option(None, "--type"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of persisted review items (read-only; ids + digests + bounded excerpts)."""
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository

    repo = ReviewRepository(_db_path(db))
    items = repo.list_review_items(review_state=state, review_type=review_type, limit=limit)
    _emit({"format": "json", "count": len(items), "items": items}, json_out=json_out)


@app.command("disposition")
def disposition(
    item_id: str = typer.Option(..., "--item-id"),
    accept: bool = typer.Option(False, "--accept"),
    reject: bool = typer.Option(False, "--reject"),
    defer: bool = typer.Option(False, "--defer"),
    not_required: bool = typer.Option(False, "--not-required"),
    request_context: bool = typer.Option(False, "--request-context"),
    reason: Optional[str] = typer.Option(None, "--reason"),
    operator_id: Optional[str] = typer.Option(None, "--operator-id"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Record a local/operator disposition (append-only). Only ``--apply`` persists (review tables only).

    Overlay-only: this changes the review effective state and NOTHING else — it never mutates a source
    record, executes an action, sends a notification, or calls N8D.
    """
    from hb_assistant.obsidian_mcp import review_disposition as rd
    from hb_assistant.obsidian_mcp.review_models import ReviewValidationError
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository

    chosen = [name for name, on in (("accept", accept), ("reject", reject), ("defer", defer),
                                    ("not_required", not_required),
                                    ("request_context", request_context)) if on]
    if len(chosen) != 1:
        _emit({"error": "exactly_one_disposition_flag_required",
               "allowed": list(_DISPOSITIONS)}, json_out=json_out, exit_code=1)
    disposition_type = _DISPOSITIONS[chosen[0]]
    repo = ReviewRepository(_db_path(db))
    try:
        result = rd.apply_disposition(repo, review_item_id=item_id, disposition_type=disposition_type,
                                      operator_id=operator_id, reason=reason, apply=not dry_run,
                                      created_by="cli")
    except ReviewValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)
