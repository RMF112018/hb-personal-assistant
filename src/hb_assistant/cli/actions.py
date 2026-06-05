"""actions subcommand group (Phase 14 Prompt 02 foundation).

extract --dry-run --json : deterministic preview (safe, no DB mutation on dry)
list --json : recent open actions (redacted, via store)

Follows exact CLI patterns from diagnostics/run/files (Typer, structured JSON, ledger, StoreReadinessError handling, no full content).
"""

from __future__ import annotations

import json
from typing import Any

import typer

from hb_assistant.actions.service import ActionService
from hb_assistant.store.errors import StoreReadinessError

app = typer.Typer(
    help="Action intelligence (local deterministic extraction + source-linked provenance). Dry-run safe by design."
)


@app.command("extract")
def extract_cmd(
    dry_run: bool = typer.Option(
        True, "--dry-run", help="Preview only; never mutates DB when true (default)"
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)"),
) -> None:
    """Extract action candidates (deterministic, source-linked). Dry-run is provably safe."""
    svc = ActionService()
    try:
        cands = svc.extract(dry_run=dry_run)
        results: list[dict[str, Any]] = [c.model_dump() for c in cands]
        # Redaction: titles are short excerpts only; no bodies/files ever
        for r in results:
            if len(r.get("title", "")) > 120:
                r["title"] = r["title"][:117] + "..."

        payload: dict[str, Any] = {
            "command": "actions extract",
            "mode": "real",
            "dry_run": dry_run,
            "results": results,
            "count": len(results),
            "note": "dry-run: preview only; no writes to action_items or source_links"
            if dry_run
            else "persisted with source links",
        }
        if dry_run:
            payload["would_persist"] = len(results)
        typer.echo(
            json.dumps(payload, indent=2, default=str)
            if json_out
            else f"extracted {len(results)} candidates"
        )
    except StoreReadinessError as e:
        payload = {"error": "StoreReadinessError", "command": "actions extract", "detail": str(e)}
        typer.echo(json.dumps(payload, indent=2) if json_out else f"error: {e}")
        raise typer.Exit(1) from e


@app.command("list")
def list_cmd(
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)"),
    limit: int = typer.Option(20, "--limit", help="Max recent items"),
) -> None:
    """List recent open action items (redacted excerpts + provenance only)."""
    svc = ActionService()
    try:
        items = svc.list_recent(limit=limit)
        results = [i.model_dump() for i in items]
        for r in results:
            if len(r.get("title", "")) > 120:
                r["title"] = r["title"][:117] + "..."
        payload = {
            "command": "actions list",
            "mode": "real",
            "results": results,
            "count": len(results),
            "note": "open actions only; full content never emitted",
        }
        typer.echo(
            json.dumps(payload, indent=2, default=str) if json_out else f"{len(results)} actions"
        )
    except StoreReadinessError as e:
        payload = {"error": "StoreReadinessError", "command": "actions list", "detail": str(e)}
        typer.echo(json.dumps(payload, indent=2) if json_out else f"error: {e}")
        raise typer.Exit(1) from e
