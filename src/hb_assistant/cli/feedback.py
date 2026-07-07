"""`hb-assistant feedback` — opt-in, bounded operator feedback capture + review-loop recommendations (N8C-18).

Records bounded operator feedback on existing N8C artifacts and derives ADVISORY, operator-review-required
review-loop recommendations. There is no background writer and no scheduler auto-start. Feedback NEVER
changes a review disposition, mutates a source/workflow/packet/draft/projection/context-pack/decision/
preference/open-loop record, stages an action, or executes anything.

``list`` / ``show`` / ``recommendations`` / ``export`` and ``add --dry-run`` are fully read-only. Only
``add --apply`` persists, and only into the five N8C-18 feedback tables. There is no accept/reject/defer/
dispose/execute/send/schedule/task/remind command.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Opt-in bounded operator feedback + advisory review-loop recommendations.")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _one_target(target_kind: Optional[str], target_id: Optional[str], review_state: Optional[str],
                effective_state: Optional[str]) -> list[dict[str, Any]]:
    if not target_kind or not target_id:
        return []
    t: dict[str, Any] = {"target_kind": target_kind, "target_id": target_id}
    if review_state:
        t["review_state"] = review_state
    if effective_state:
        t["effective_state"] = effective_state
    return [t]


@app.command("add")
def add(
    feedback_type: str = typer.Option(..., "--feedback-type",
        help="needs_review | wrong_review_label | wrong_source | duplicate | operator_note | ..."),
    target_kind: str = typer.Option(..., "--target-kind",
        help="open_loop | review_item | citation | source_ref | answer_draft | workflow_result | ..."),
    target_id: str = typer.Option(..., "--target-id"),
    note: Optional[str] = typer.Option(None, "--note"),
    workflow_type: Optional[str] = typer.Option(None, "--workflow-type"),
    workflow_id: Optional[str] = typer.Option(None, "--workflow-id"),
    review_state: Optional[str] = typer.Option(None, "--review-state"),
    effective_state: Optional[str] = typer.Option(None, "--effective-state"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Capture bounded operator feedback; only ``--apply`` persists (feedback tables only)."""
    from hb_assistant.obsidian_mcp import feedback_service as fs
    from hb_assistant.obsidian_mcp.feedback_models import FeedbackValidationError
    from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository

    targets = _one_target(target_kind, target_id, review_state, effective_state)
    try:
        result = fs.capture_feedback(
            FeedbackRepository(_db_path(db)), feedback_type=feedback_type, targets=targets, note=note,
            workflow_type=workflow_type, workflow_id=workflow_id, created_by="cli", apply=not dry_run)
    except FeedbackValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("list")
def list_feedback(
    feedback_type: Optional[str] = typer.Option(None, "--feedback-type"),
    status: Optional[str] = typer.Option(None, "--status"),
    workflow_id: Optional[str] = typer.Option(None, "--workflow-id"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted feedback records."""
    from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository

    repo = FeedbackRepository(_db_path(db))
    records = repo.list_feedback(feedback_type=feedback_type, status=status, workflow_id=workflow_id,
                                 limit=limit)
    _emit({"feedback": records, "count": len(records)}, json_out=json_out)


@app.command("show")
def show(
    feedback_id: str = typer.Option(..., "--feedback-id"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only view of one feedback record + its targets + recommendations."""
    from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository

    repo = FeedbackRepository(_db_path(db))
    record = repo.get_feedback(feedback_id)
    if record is None:
        _emit({"error": f"feedback_not_found:{feedback_id}"}, json_out=json_out, exit_code=1)
    _emit({"feedback": record, "targets": repo.list_targets(feedback_id, limit=limit),
           "recommendations": repo.list_recommendations(feedback_id, limit=limit)}, json_out=json_out)


@app.command("recommendations")
def recommendations(
    feedback_id: Optional[str] = typer.Option(None, "--feedback-id"),
    recommendation_type: Optional[str] = typer.Option(None, "--type"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of ADVISORY review-loop recommendations."""
    from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository

    repo = FeedbackRepository(_db_path(db))
    recs = repo.list_recommendations(feedback_id, recommendation_type=recommendation_type, limit=limit)
    _emit({"recommendations": recs, "count": len(recs)}, json_out=json_out)


@app.command("export")
def export(
    feedback_id: str = typer.Option(..., "--feedback-id"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted feedback record (read-only). No raw bodies, no full payloads."""
    from hb_assistant.obsidian_mcp import feedback_service as fs
    from hb_assistant.obsidian_mcp.feedback_models import FeedbackValidationError
    from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository

    try:
        _emit(fs.export_feedback(FeedbackRepository(_db_path(db)), feedback_id=feedback_id, limit=limit),
              json_out=json_out)
    except FeedbackValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
