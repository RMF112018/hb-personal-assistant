"""N8C-19 `hb-assistant action-stage` CLI: preview (RO), build (dry-run default / --apply write), list, show,
export are the only commands; the write gate is a single --dry-run/--apply flag; no execute/send/schedule/
dispatch/remind/task command exists."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.action_stage import app
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()


def _db(tmp_path: Path) -> str:
    db = tmp_path / "as.db"
    SQLiteMigrator(db_path=str(db)).apply()
    fs.capture_feedback(FeedbackRepository(str(db)), feedback_type="needs_review",
                        targets=[{"target_kind": "open_loop", "target_id": "OL1", "open_loop_id": "OL1"}],
                        apply=True)
    return str(db)


def _build(db: str, *, apply: bool) -> dict:
    args = ["build", "--workflow-type", "open_loop_triage", "--db", db, "--json"]
    args.append("--apply" if apply else "--dry-run")
    res = runner.invoke(app, args)
    assert res.exit_code == 0, res.output
    return json.loads(res.output)


def test_preview_is_read_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = runner.invoke(app, ["preview", "--workflow-type", "open_loop_triage", "--db", db, "--json"])
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
    sid = out["stage_id"]
    listed = json.loads(runner.invoke(app, ["list", "--db", db, "--json"]).output)
    assert listed["count"] == 1
    shown = json.loads(runner.invoke(app, ["show", "--stage-id", sid, "--db", db, "--json"]).output)
    assert shown["stage"]["stage_id"] == sid
    # every shown item is non-executing
    for it in shown["items"]:
        assert it["execution_status"] == "not_executed" and it["external_ref"] is None


def test_export_is_read_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    sid = _build(db, apply=True)["stage_id"]
    exported = json.loads(
        runner.invoke(app, ["export", "--stage-id", sid, "--db", db, "--json"]).output)
    assert exported["format"] == "action_stage_export_v1"


def test_no_execution_commands() -> None:
    names = {c.name for c in app.registered_commands}
    assert names == {"preview", "build", "list", "show", "export"}
    for banned in ("execute", "send", "schedule", "dispatch", "remind", "task", "apply", "run"):
        assert banned not in names
