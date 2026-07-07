"""`hb-assistant workflow` — N8C-15 read-only workflow contract + routing.

``catalog`` dumps the canonical workflow registry (types, routing targets, deferred markers). ``route``
accepts a bounded workflow request and returns the normalized routing envelope over EXISTING N8C read
surfaces. Both commands are fully read-only: nothing is persisted, no workflow run/history is recorded, no
build/apply writer is called, no live source read occurs, no action is executed, and no MCP tool is added.
There is no ``--apply`` / ``--build`` / ``--execute`` / ``--send`` flag anywhere in this group.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Read-only N8C workflow contract + routing (route-only, never executes).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


@app.command("catalog")
def catalog(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only dump of the workflow registry catalog (no DB access)."""
    from hb_assistant.obsidian_mcp.workflow_registry import catalog as _catalog

    _emit(_catalog(), json_out=json_out)


@app.command("route")
def route(
    workflow_type: Optional[str] = typer.Option(None, "--workflow-type"),
    query: Optional[str] = typer.Option(None, "--query"),
    objective: Optional[str] = typer.Option(None, "--objective"),
    domain: Optional[str] = typer.Option(None, "--domain"),
    project_key: Optional[str] = typer.Option(None, "--project-key"),
    source_root_key: Optional[str] = typer.Option(None, "--source-root-key"),
    draft_id: Optional[str] = typer.Option(None, "--draft-id"),
    packet_id: Optional[str] = typer.Option(None, "--packet-id"),
    projection_id: Optional[str] = typer.Option(None, "--projection-id"),
    context_pack_id: Optional[str] = typer.Option(None, "--context-pack-id"),
    review_item_id: Optional[str] = typer.Option(None, "--review-item-id"),
    memory_node_id: Optional[str] = typer.Option(None, "--memory-node-id"),
    decision_id: Optional[str] = typer.Option(None, "--decision-id"),
    preference_id: Optional[str] = typer.Option(None, "--preference-id"),
    open_loop_id: Optional[str] = typer.Option(None, "--open-loop-id"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Route a bounded workflow request to existing N8C read surfaces (read-only; no execution)."""
    from hb_assistant.obsidian_mcp.workflow_models import WorkflowRequest
    from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter

    request = WorkflowRequest.from_inputs(
        workflow_type=workflow_type, query=query, objective=objective, domain=domain,
        project_key=project_key, source_root_key=source_root_key, draft_id=draft_id, packet_id=packet_id,
        projection_id=projection_id, context_pack_id=context_pack_id, review_item_id=review_item_id,
        memory_node_id=memory_node_id, decision_id=decision_id, preference_id=preference_id,
        open_loop_id=open_loop_id, requested_by="cli")
    _emit(WorkflowRouter(_db_path(db)).route(request), json_out=json_out)
