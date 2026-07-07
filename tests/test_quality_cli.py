"""N8C-20 `hb-assistant quality` CLI: preview (RO), build (dry-run default / --apply write), list, show,
summary, export are the only commands; the write gate is a single --dry-run/--apply flag; no
execute/repair/send/schedule/accept/reject command exists."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.quality import app
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()


def _db(tmp_path: Path) -> str:
    db = tmp_path / "q.db"
    SQLiteMigrator(db_path=str(db)).apply()
    fs.capture_feedback(FeedbackRepository(str(db)), feedback_type="needs_review",
                        targets=[{"target_kind": "open_loop", "target_id": "OL1", "open_loop_id": "OL1"}],
                        apply=True)
    return str(db)


def _build(db: str, *, apply: bool) -> dict:
    args = ["build", "--target-kind", "action_stage", "--target-id", "S-missing", "--db", db, "--json"]
    args.append("--apply" if apply else "--dry-run")
    res = runner.invoke(app, args)
    assert res.exit_code == 0, res.output
    return json.loads(res.output)


def test_preview_is_read_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = runner.invoke(app, ["preview", "--target-kind", "action_stage", "--target-id", "S-x",
                              "--db", db, "--json"])
    assert res.exit_code == 0
    plan = json.loads(res.output)
    assert plan["mode"] == "preview" and plan["applied"] is False
    assert json.loads(runner.invoke(app, ["list", "--db", db, "--json"]).output)["count"] == 0


def test_build_dry_run_default_persists_nothing(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = _build(db, apply=False)
    assert out["mode"] == "dry_run" and out["applied"] is False
    assert json.loads(runner.invoke(app, ["list", "--db", db, "--json"]).output)["count"] == 0


def test_build_apply_persists_and_shows(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = _build(db, apply=True)
    assert out["mode"] == "apply" and out["applied"] is True
    qid = out["quality_run_id"]
    listed = json.loads(runner.invoke(app, ["list", "--db", db, "--json"]).output)
    assert listed["count"] == 1
    shown = json.loads(runner.invoke(app, ["show", "--quality-run-id", qid, "--db", db, "--json"]).output)
    assert shown["run"]["quality_run_id"] == qid
    assert shown["run"]["status"] == "evaluated"
    for f in shown["findings"]:
        assert f["requires_operator_review"] == 1 and f["execution_policy"] == "evaluate_only"


def test_summary_and_export_are_read_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    qid = _build(db, apply=True)["quality_run_id"]
    summary = json.loads(runner.invoke(app, ["summary", "--db", db, "--json"]).output)
    assert summary["total_runs"] == 1
    exported = json.loads(
        runner.invoke(app, ["export", "--quality-run-id", qid, "--db", db, "--json"]).output)
    assert exported["format"] == "quality_export_v1"


def test_no_execution_or_disposition_commands() -> None:
    names = {c.name for c in app.registered_commands}
    assert names == {"preview", "build", "list", "show", "summary", "export"}
    for banned in ("execute", "repair", "send", "schedule", "dispatch", "remind", "task", "apply",
                   "accept", "reject", "defer", "dispose", "run"):
        assert banned not in names
