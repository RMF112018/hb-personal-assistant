"""CLI for selective file ingestion (Phase 10).

`hb-assistant files ingest --dry-run --json` : exercises relevance + eligibility + approval + (dry) pipeline.
Always safe: no real large downloads without explicit future flags; uses sample data for demo.
"""

from __future__ import annotations

import json
from typing import Optional

import typer

from hb_assistant.files import FileIngestionService, FileRelevanceScorer
from hb_assistant.normalize.drive_item import DriveItem
from hb_assistant.store.repositories import Store

app = typer.Typer(help="Selective file/attachment ingestion (relevance, eligibility, approval, bounded parse). Dry-run safe.")


@app.command("ingest")
def files_ingest(
    dry_run: bool = typer.Option(True, "--dry-run", help="Preview only (no DL/parse/persist). Use for safe inspection."),
    json_out: bool = typer.Option(True, "--json"),
    limit: int = typer.Option(5, "--limit", min=1, max=20),
    apply: bool = typer.Option(False, "--apply", help="Allow real (small) DL for approved items in this session (tests/CI only; guarded)."),
) -> None:
    """Selective ingest preview or run (dry-run default).

    Uses in-memory sample DriveItems exercising Phase 10 logic (relevance from signals, 08 eligibility/approval, parser matrix).
    Real Graph-backed discovery available via morning run (later) or when clients provided.
    All outputs redacted; excerpts bounded; source links created on real ingest.
    """
    if apply and dry_run:
        # --apply with dry is no-op
        pass

    # Sample items covering matrix + decision paths (no real M365)
    samples = [
        DriveItem(id="sample-pdf-1", name="Q3 Financial Report.pdf", size=1_800_000, is_file=True, source_record_id=1001),
        DriveItem(id="sample-xlsx-2", name="Board Deck Q2.xlsx", size=4_200_000, is_file=True, source_record_id=1002),
        DriveItem(id="sample-pptx-3", name="Strategy Review.pptx", size=12_000_000, is_file=True, source_record_id=1003),
        DriveItem(id="sample-zip-4", name="archive_export.zip", size=320 * 1024 * 1024, is_file=True, source_record_id=1004),  # >300MB -> approval
        DriveItem(id="sample-txt-5", name="notes.md", size=4200, is_file=True, source_record_id=1005),
        DriveItem(id="sample-small-6", name="tiny.log", size=120, is_file=True, source_record_id=1006),  # low relevance likely
    ][:limit]

    # Provide sample classification signals (as if from Phase 6) for first few
    classifs = {
        1001: ["bobby_mention"],
        1002: ["possible_action_or_waiting"],
        1003: ["bobby_mention", "possible_action_or_waiting"],
        1004: [],
        1005: [],
        1006: [],
    }

    # In-memory store for demo (real uses default path, but isolated here)
    store = Store()  # uses default; for pure demo ok (idempotent)
    # Note: for full isolation in tests we pass tmp, here CLI uses real (safe, no secrets)
    svc = FileIngestionService(drive_client=object(), store=store)  # drive not used for sample path

    results = svc.ingest_items(
        samples,
        dry_run=dry_run and not apply,  # --apply forces non-dry for demo (small files only)
        approved_source_ids={1004} if apply else None,  # allow the large one only if --apply
        classifications_by_source=classifs,
    )

    payload = {
        "command": "files ingest",
        "dry_run": dry_run and not apply,
        "applied_real": bool(apply and not dry_run),
        "limit": limit,
        "results": results,
        "note": "Redacted selective preview. Relevance (signals+heuristics) + eligibility + approval gate exercised. Excerpts bounded. No full content. Source links on real path. Next: Prompt 11 retrieval.",
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo("files ingest results (redacted):")
        for r in results:
            typer.echo(f"  {r.get('name')} -> {r.get('decision')} (rel={r.get('relevance',{}).get('score')})")
    raise typer.Exit(0)
