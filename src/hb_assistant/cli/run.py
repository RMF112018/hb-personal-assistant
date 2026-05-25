"""Run CLI subcommands (canonical grammar).

Canonical command:
- hb-assistant run morning --dry-run --json
"""

from __future__ import annotations

import json
from typing import Any, Dict

import typer

app = typer.Typer(help="Run workflows (morning orchestrator and related runtime commands).")


@app.command("morning")
def morning_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Run in dry-run mode."),
    json_out: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """Execute morning workflow via orchestrator (Phase 12)."""
    from hb_assistant.links.registry import SourceLinkRegistry

    reg = SourceLinkRegistry()
    run_id = reg.record_run(
        run_type="morning",
        target_date="today",
        trigger="cli",
        dry_run=dry_run,
        status="started",
    )

    try:
        from hb_assistant.automation.orchestrator import MorningRunOrchestrator

        orch = MorningRunOrchestrator()
        orch_result = orch.run(dry_run=dry_run)
        reg.finish_run(run_id, status="completed-dry-run" if dry_run else "completed")
        payload: Dict[str, Any] = {
            "implemented": True,
            "phase": 12,
            "run_id": run_id,
            "orchestrator": orch_result,
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else "run morning: orchestrator completed (see json for details)")
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as ex:  # pragma: no cover
        reg.finish_run(run_id, status="error")
        payload = {"error": str(ex)[:200], "run_id": run_id, "note": "orchestrator failed; ledger updated"}
        typer.echo(json.dumps(payload, indent=2) if json_out else f"run morning error: {ex}")
        raise typer.Exit(1)
