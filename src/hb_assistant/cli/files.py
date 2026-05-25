"""CLI for selective file ingestion (Phase 10 remediation).

- `hb-assistant files sample --json` uses synthetic records for demo only.
- `hb-assistant files ingest --dry-run --json` uses real persisted provenance-backed candidates only.
"""

from __future__ import annotations

import json
from typing import Optional

import typer

from hb_assistant.files import FileIngestionService
from hb_assistant.normalize.drive_item import DriveItem
from hb_assistant.store.repositories import Store
from hb_assistant.store.errors import StoreReadinessError

app = typer.Typer(help="Selective file/attachment ingestion (relevance, eligibility, approval, bounded parse). Dry-run safe.")


def _sample_items(limit: int) -> list[DriveItem]:
    samples = [
        DriveItem(id="sample-pdf-1", name="Q3 Financial Report.pdf", size=1_800_000, is_file=True, source_record_id=1001),
        DriveItem(id="sample-xlsx-2", name="Board Deck Q2.xlsx", size=4_200_000, is_file=True, source_record_id=1002),
        DriveItem(id="sample-pptx-3", name="Strategy Review.pptx", size=12_000_000, is_file=True, source_record_id=1003),
        DriveItem(id="sample-zip-4", name="archive_export.zip", size=320 * 1024 * 1024, is_file=True, source_record_id=1004),  # >300MB -> approval
        DriveItem(id="sample-txt-5", name="notes.md", size=4200, is_file=True, source_record_id=1005),
        DriveItem(id="sample-small-6", name="tiny.log", size=120, is_file=True, source_record_id=1006),  # low relevance likely
    ][:limit]
    return samples


def _sample_classifications() -> dict[int, list[str]]:
    classifs = {
        1001: ["bobby_mention"],
        1002: ["possible_action_or_waiting"],
        1003: ["bobby_mention", "possible_action_or_waiting"],
        1004: [],
        1005: [],
        1006: [],
    }
    return classifs


@app.command("sample")
def files_sample(
    json_out: bool = typer.Option(True, "--json"),
    limit: int = typer.Option(5, "--limit", min=1, max=20),
) -> None:
    """Synthetic demo path only; never performs real download/parse/persist."""
    try:
        svc = FileIngestionService(drive_client=object(), store=Store())
    except Exception as ex:
        payload = {
            "command": "files sample",
            "mode": "sample",
            "status": "runtime_error",
            "error": str(ex)[:200],
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        raise typer.Exit(1)
    results = svc.ingest_items(
        _sample_items(limit),
        dry_run=True,
        classifications_by_source=_sample_classifications(),
    )
    payload = {
        "command": "files sample",
        "mode": "sample",
        "dry_run": True,
        "limit": limit,
        "results": results,
        "note": "Synthetic records only. No real candidate discovery, download, parse, or persist.",
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo("files sample results (redacted):")
        for r in results:
            typer.echo(f"  {r.get('name')} -> {r.get('decision')} (rel={r.get('relevance',{}).get('score')})")
    raise typer.Exit(0)


@app.command("ingest")
def files_ingest(
    dry_run: bool = typer.Option(True, "--dry-run", help="Preview only (no DL/parse/persist). Use for safe inspection."),
    json_out: bool = typer.Option(True, "--json"),
    limit: int = typer.Option(5, "--limit", min=1, max=20),
    apply: bool = typer.Option(False, "--apply", help="Allow real (small) DL for approved items in this session (tests/CI only; guarded)."),
) -> None:
    """Real provenance-backed ingest path (dry-run default)."""
    try:
        store = Store()
    except StoreReadinessError as ex:
        payload = {
            "command": "files ingest",
            "mode": "real",
            "status": "blocked_db_unavailable",
            "dry_run": dry_run and not apply,
            "limit": limit,
            "results": [],
            "error": ex.message[:200],
            "db_path": ex.db_path,
            "readiness": ex.report,
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        raise typer.Exit(1)
    except Exception as ex:
        payload = {
            "command": "files ingest",
            "mode": "real",
            "status": "runtime_error",
            "dry_run": dry_run and not apply,
            "limit": limit,
            "results": [],
            "error": str(ex)[:200],
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        raise typer.Exit(1)
    svc = FileIngestionService(drive_client=object(), store=store)
    candidates = []
    try:
        for row in store.list_pending_ingest_candidates(limit=limit):
            candidates.append(
                DriveItem(
                    id=str(row.get("drive_item_id") or ""),
                    name=row.get("name"),
                    size=row.get("size_bytes"),
                    web_url=row.get("web_url"),
                    is_file=True,
                    source_record_id=row.get("source_record_id"),
                )
            )
    except StoreReadinessError as ex:
        payload = {
            "command": "files ingest",
            "mode": "real",
            "status": "blocked_db_unavailable",
            "dry_run": dry_run and not apply,
            "limit": limit,
            "results": [],
            "error": ex.message[:200],
            "db_path": ex.db_path,
            "readiness": ex.report,
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        raise typer.Exit(1)
    except Exception as ex:
        payload = {
            "command": "files ingest",
            "mode": "real",
            "status": "candidate_discovery_error",
            "dry_run": dry_run and not apply,
            "limit": limit,
            "results": [],
            "error": str(ex)[:200],
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        raise typer.Exit(1)

    if not candidates:
        payload = {
            "command": "files ingest",
            "mode": "real",
            "status": "no_provenance_candidates",
            "dry_run": dry_run and not apply,
            "limit": limit,
            "results": [],
            "note": "No persisted provenance-backed file candidates found. Run discovery/persistence flows first.",
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        raise typer.Exit(1)

    results = svc.ingest_items(
        candidates,
        dry_run=dry_run and not apply,  # --apply forces non-dry for demo (small files only)
        approved_source_ids=set() if not apply else None,
    )

    payload = {
        "command": "files ingest",
        "mode": "real",
        "status": "ok",
        "dry_run": dry_run and not apply,
        "applied_real": bool(apply and not dry_run),
        "limit": limit,
        "results": results,
        "note": "Real persisted provenance-backed candidate ingestion. No synthetic fallback in this command.",
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo("files ingest results (redacted):")
        for r in results:
            typer.echo(f"  {r.get('name')} -> {r.get('decision')} (rel={r.get('relevance',{}).get('score')})")
    raise typer.Exit(0)
