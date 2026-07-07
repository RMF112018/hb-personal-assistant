"""`hb-assistant quality` — deterministic, read-only EVALUATION of existing N8C records (N8C-20).

The evaluator READS one existing N8C target (action stage, feedback record, answer draft, research packet,
workflow route, review item) and emits **advisory** quality findings (freshness / citation coverage /
review-state consistency / source-ref validity / policy compliance / duplication / boundedness). It NEVER
rebuilds an artifact, repairs anything, executes anything, stages an action, writes a review disposition,
mutates any upstream record, contacts an external system, reads a source file, or calls an LLM. There is no
repair / execute / send / schedule / task / remind / accept / reject / defer / dispose command. ``preview`` /
``list`` / ``show`` / ``export`` are fully read-only; only ``build --apply`` persists, and only into the five
N8C-20 ``assistant_quality_*`` tables. ``evaluated`` is a run-record lifecycle status only.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

app = typer.Typer(help="Evaluate existing N8C records and emit ADVISORY quality findings (no execution).")


def _emit(payload: dict[str, Any], *, json_out: bool, exit_code: int = 0) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(exit_code)


def _db_path(db: Optional[str]) -> str:
    if db:
        return db
    from hb_assistant.config.path_policy import PathPolicy

    return str(PathPolicy().get_db_path())


def _providers(db: str):
    """Read-only providers over existing N8C repositories (any may be absent → that kind yields fewer checks)."""
    from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository
    from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository
    from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
    from hb_assistant.obsidian_mcp.quality_evaluator import QualityProviders
    from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
    from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter

    return QualityProviders(
        action_stage_repo=ActionStageRepository(db),
        feedback_repo=FeedbackRepository(db),
        draft_repo=AnswerDraftRepository(db),
        packet_repo=ResearchPacketRepository(db),
        review_repo=ReviewRepository(db),
        source_repo=SourceIndexRepository(db),
        router=WorkflowRouter(db),
    )


@app.command("preview")
def preview(
    target_kind: str = typer.Option(..., "--target-kind",
        help="action_stage | feedback | answer_draft | workflow | research_packet | review_item | ..."),
    target_id: str = typer.Option(..., "--target-id"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only: evaluate one target and assemble the full advisory finding plan WITHOUT persisting."""
    from hb_assistant.obsidian_mcp import quality_evaluator as E
    from hb_assistant.obsidian_mcp.quality_models import QualityValidationError

    try:
        plan = E.preview_quality(_providers(_db_path(db)), target_kind=target_kind, target_id=target_id,
                                 created_by="cli")
    except QualityValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    plan["mode"] = "preview"
    _emit(plan, json_out=json_out)


@app.command("build")
def build(
    target_kind: str = typer.Option(..., "--target-kind"),
    target_id: str = typer.Option(..., "--target-id"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run persists nothing."),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Evaluate a target; only ``--apply`` persists (into the five quality tables only). No execution/repair."""
    from hb_assistant.obsidian_mcp import quality_evaluator as E
    from hb_assistant.obsidian_mcp.quality_models import QualityValidationError
    from hb_assistant.obsidian_mcp.quality_repository import QualityRepository

    path = _db_path(db)
    try:
        result = E.build_quality(_providers(path), QualityRepository(path), target_kind=target_kind,
                                 target_id=target_id, apply=not dry_run, created_by="cli")
    except QualityValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
    result["mode"] = "dry_run" if dry_run else "apply"
    _emit(result, json_out=json_out)


@app.command("list")
def list_runs(
    target_kind: Optional[str] = typer.Option(None, "--target-kind"),
    target_id: Optional[str] = typer.Option(None, "--target-id"),
    status: Optional[str] = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only list of persisted quality runs."""
    from hb_assistant.obsidian_mcp.quality_repository import QualityRepository

    repo = QualityRepository(_db_path(db))
    runs = repo.list_quality_runs(target_kind=target_kind, target_id=target_id, status=status, limit=limit)
    _emit({"quality_runs": runs, "count": len(runs)}, json_out=json_out)


@app.command("show")
def show(
    quality_run_id: str = typer.Option(..., "--quality-run-id"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only view of one quality run + its advisory findings + evaluated targets."""
    from hb_assistant.obsidian_mcp.quality_repository import QualityRepository

    repo = QualityRepository(_db_path(db))
    run = repo.get_quality_run(quality_run_id)
    if run is None:
        _emit({"error": f"quality_run_not_found:{quality_run_id}"}, json_out=json_out, exit_code=1)
    _emit({"run": run, "findings": repo.list_findings(quality_run_id, limit=limit),
           "targets": repo.list_targets(quality_run_id, limit=limit)}, json_out=json_out)


@app.command("summary")
def summary(
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only bounded aggregate across quality runs (counts by kind / status / finding-type / severity)."""
    from hb_assistant.obsidian_mcp.quality_repository import QualityRepository

    _emit(QualityRepository(_db_path(db)).summary(), json_out=json_out)


@app.command("export")
def export(
    quality_run_id: str = typer.Option(..., "--quality-run-id"),
    limit: int = typer.Option(200, "--limit"),
    db: Optional[str] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Bounded JSON export of a persisted quality run (read-only). No bodies, no repair/execution fields."""
    from hb_assistant.obsidian_mcp import quality_evaluator as E
    from hb_assistant.obsidian_mcp.quality_models import QualityValidationError
    from hb_assistant.obsidian_mcp.quality_repository import QualityRepository

    try:
        _emit(E.export_quality(QualityRepository(_db_path(db)), quality_run_id=quality_run_id, limit=limit),
              json_out=json_out)
    except QualityValidationError as e:
        _emit({"error": str(e)}, json_out=json_out, exit_code=1)
