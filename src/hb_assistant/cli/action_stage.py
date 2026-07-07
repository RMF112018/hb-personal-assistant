"""`hb-assistant action-stage` — deterministic, source-backed, operator-review-required staging of proposed
follow-up CANDIDATES over the N8C-17 workflow context + N8C-18 advisory feedback (N8C-19).

Staging is NOT execution. Every staged item is a candidate/blocked follow-up pinned to not_executed /
external_system=none / requires_operator_review=1. There is no send/schedule/execute/dispatch/remind/task
command, no external-system integration, and no review-disposition write. ``preview`` / ``list`` / ``show`` /
``export`` are fully read-only; only ``build --apply`` persists, and only into the five N8C-19 stage tables.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Stage proposed follow-up CANDIDATES (no execution) over workflow context + feedback.")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _providers(db: str):
    from hb_assistant.obsidian_mcp.action_stage_builder import ActionStageProviders
    from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
    from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter

    return ActionStageProviders(router=WorkflowRouter(db), feedback_repo=FeedbackRepository(db))


def _request_inputs(workflow_type: Optional[str], query: Optional[str], objective: Optional[str],
                    project_key: Optional[str], open_loop_id: Optional[str]) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for key, val in (("workflow_type", workflow_type), ("query", query), ("objective", objective),
                     ("project_key", project_key), ("open_loop_id", open_loop_id)):
        if val:
            inputs[key] = val
    return inputs


@app.command("preview")
def preview(
    workflow_type: Optional[str] = typer.Option(None, "--workflow-type",
        help="daily_brief_context | meeting_prep | project_intelligence_context | open_loop_triage | ..."),
    query: Optional[str] = typer.Option(None, "--query"),
    objective: Optional[str] = typer.Option(None, "--objective"),
    project_key: Optional[str] = typer.Option(None, "--project-key"),
    open_loop_id: Optional[str] = typer.Option(None, "--open-loop-id"),
    stage_type: Optional[str] = typer.Option(None, "--stage-type"),
    include_feedback: bool = typer.Option(True, "--include-feedback/--no-feedback"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only: assemble the full stage plan (candidates + blocked + citations) WITHOUT persisting."""
    from hb_assistant.obsidian_mcp import action_stage_builder as B
    from hb_assistant.obsidian_mcp.action_stage_models import ActionStageValidationError

    inputs = _request_inputs(workflow_type, query, objective, project_key, open_loop_id)
    try:
        plan = B.preview_action_stage(_providers(_db_path(db)), request_inputs=inputs, stage_type=stage_type,
                                      include_feedback=include_feedback, created_by="cli")
    except ActionStageValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    plan["mode"] = "preview"
    _emit(plan, json_out=json_out)


@app.command("build")
def build(
    workflow_type: Optional[str] = typer.Option(None, "--workflow-type"),
    query: Optional[str] = typer.Option(None, "--query"),
    objective: Optional[str] = typer.Option(None, "--objective"),
    project_key: Optional[str] = typer.Option(None, "--project-key"),
    open_loop_id: Optional[str] = typer.Option(None, "--open-loop-id"),
    stage_type: Optional[str] = typer.Option(None, "--stage-type"),
    include_feedback: bool = typer.Option(True, "--include-feedback/--no-feedback"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a stage; only ``--apply`` persists (into the five stage tables only). No execution."""
    from hb_assistant.obsidian_mcp import action_stage_builder as B
    from hb_assistant.obsidian_mcp.action_stage_models import ActionStageValidationError
    from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository

    path = _db_path(db)
    inputs = _request_inputs(workflow_type, query, objective, project_key, open_loop_id)
    try:
        result = B.build_action_stage(_providers(path), ActionStageRepository(path), request_inputs=inputs,
                                      stage_type=stage_type, include_feedback=include_feedback,
                                      apply=not dry_run, created_by="cli")
    except ActionStageValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("list")
def list_stages(
    stage_type: Optional[str] = typer.Option(None, "--stage-type"),
    status: Optional[str] = typer.Option(None, "--status"),
    workflow_type: Optional[str] = typer.Option(None, "--workflow-type"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted stages."""
    from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository

    repo = ActionStageRepository(_db_path(db))
    stages = repo.list_stages(stage_type=stage_type, status=status, workflow_type=workflow_type, limit=limit)
    _emit({"stages": stages, "count": len(stages)}, json_out=json_out)


@app.command("show")
def show(
    stage_id: str = typer.Option(..., "--stage-id"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only view of one stage + its items + citations."""
    from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository

    repo = ActionStageRepository(_db_path(db))
    stage = repo.get_stage(stage_id)
    if stage is None:
        _emit({"error": f"stage_not_found:{stage_id}"}, json_out=json_out, exit_code=1)
    _emit({"stage": stage, "items": repo.list_items(stage_id, limit=limit),
           "citations": repo.list_citations(stage_id, limit=limit)}, json_out=json_out)


@app.command("export")
def export(
    stage_id: str = typer.Option(..., "--stage-id"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted stage (read-only). No bodies, no execution fields, no external refs."""
    from hb_assistant.obsidian_mcp import action_stage_builder as B
    from hb_assistant.obsidian_mcp.action_stage_models import ActionStageValidationError
    from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository

    try:
        _emit(B.export_action_stage(ActionStageRepository(_db_path(db)), stage_id=stage_id, limit=limit),
              json_out=json_out)
    except ActionStageValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
