"""`hb-assistant qwen-worker` — opt-in local Qwen enrichment worker (N8C-5).

Drives the enrichment queue explicitly from the command line. There is no background daemon and no
backend/scheduler auto-start: a job is only processed when an operator runs one of these commands.
Writes require ``--apply``; the default is a read-only ``--dry-run`` that persists nothing.
"""

from __future__ import annotations

import json
import socket
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in local Qwen enrichment worker (never auto-started).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _provider() -> Any:
    from hb_assistant.obsidian_mcp.enrichment_model_provider import OllamaModelProvider

    return OllamaModelProvider()


def _worker_id(explicit: Optional[str]) -> str:
    return explicit or f"cli-{socket.gethostname()}"


def _run(*, db: Optional[str], worker_id: Optional[str], lease_seconds: int, job_type: Optional[str],
         limit: int, dry_run: bool, json_out: bool) -> None:
    from hb_assistant.obsidian_mcp import qwen_worker as qw

    job_types = (job_type,) if job_type else None
    results = qw.poll_and_process(
        db_path=_db_path(db), provider=_provider(), worker_id=_worker_id(worker_id),
        limit=limit, lease_seconds=lease_seconds, job_types=job_types, dry_run=dry_run,
    )
    _emit({"mode": "dry_run" if dry_run else "apply", "processed": len(results),
           "results": results}, json_out=json_out)


@app.command("run-once")
def run_once(
    db: Optional[str] = typer.Option(None, "--db", help="SQLite path (default: app-support DB)."),
    worker_id: Optional[str] = typer.Option(None, "--worker-id"),
    lease_seconds: int = typer.Option(300, "--lease-seconds"),
    job_type: Optional[str] = typer.Option(None, "--job-type", help="Restrict to one job type."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Claim + process a single queued job (dry-run by default)."""
    _run(db=db, worker_id=worker_id, lease_seconds=lease_seconds, job_type=job_type, limit=1,
         dry_run=dry_run, json_out=json_out)


@app.command("run-batch")
def run_batch(
    db: Optional[str] = typer.Option(None, "--db"),
    worker_id: Optional[str] = typer.Option(None, "--worker-id"),
    lease_seconds: int = typer.Option(300, "--lease-seconds"),
    job_type: Optional[str] = typer.Option(None, "--job-type"),
    limit: int = typer.Option(5, "--limit", help="Max jobs to process this run."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Claim + process up to N queued jobs (dry-run by default)."""
    _run(db=db, worker_id=worker_id, lease_seconds=lease_seconds, job_type=job_type, limit=limit,
         dry_run=dry_run, json_out=json_out)


@app.command("status")
def status(
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only queue counts by status."""
    from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository

    e = EnrichmentRepository(_db_path(db))
    _emit({
        "queued": e.count_jobs(status="queued"),
        "claimed": e.count_jobs(status="claimed"),
        "running": e.count_jobs(status="running"),
        "completed": e.count_jobs(status="completed"),
        "failed": e.count_jobs(status="failed"),
        "stale": e.count_jobs(status="stale"),
        "total": e.count_jobs(),
    }, json_out=json_out)
