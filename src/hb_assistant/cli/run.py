"""Run CLI subcommands (canonical grammar).

Canonical command:
- hb-assistant run morning --dry-run --json
"""

from __future__ import annotations

import json
from typing import Any, Dict

import typer

from hb_assistant.store.errors import StoreReadinessError

app = typer.Typer(help="Run workflows (morning orchestrator and related runtime commands).")


@app.command("morning")
def morning_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Run in dry-run mode."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """Execute morning workflow via orchestrator (Phase 12)."""
    try:
        from hb_assistant.automation.orchestrator import MorningRunOrchestrator
        from hb_assistant.links.registry import SourceLinkRegistry

        reg = SourceLinkRegistry()
        run_id = reg.record_run(
            run_type="morning",
            target_date="today",
            trigger="cli",
            dry_run=dry_run,
            status="started",
        )
        orch = MorningRunOrchestrator()
        orch_result = orch.run(dry_run=dry_run)
        reg.finish_run(run_id, status="completed-dry-run" if dry_run else "completed")
        payload: Dict[str, Any] = {
            "implemented": True,
            "phase": 14,
            "run_id": run_id,
            "orchestrator": orch_result,
        }
        typer.echo(
            json.dumps(payload, indent=2, default=str)
            if json_out
            else "run morning: orchestrator completed (see json for details)"
        )
        raise typer.Exit(0)
    except StoreReadinessError as ex:
        error_payload: Dict[str, Any] = {
            "status": "blocked_db_unavailable",
            "dry_run": dry_run,
            "error": ex.message[:200],
            "db_path": ex.db_path,
            "readiness": ex.report,
            "orchestrator": {
                "status": "blocked_db_unavailable",
                "stages": [
                    {
                        "stage": "ledger_and_store",
                        "status": "skipped",
                        "reason": "db_unavailable",
                    }
                ],
            },
        }
        typer.echo(
            json.dumps(error_payload, indent=2, default=str) if json_out else str(error_payload)
        )
        raise typer.Exit(1) from ex
    except typer.Exit:
        raise
    except Exception as ex:  # pragma: no cover
        payload = {
            "error": str(ex)[:200],
            "note": "orchestrator failed before or during ledger update",
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else f"run morning error: {ex}")
        raise typer.Exit(1) from ex
