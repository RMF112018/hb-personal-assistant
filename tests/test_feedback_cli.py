"""N8C-18 `hb-assistant feedback` CLI: add (dry-run default / --apply write), list, show, recommendations,
export are the only commands; the write gate is a single --dry-run/--apply flag; no accept/reject/defer/
dispose/execute/send/schedule/stage command exists."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.feedback import app
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()


def _db(tmp_path: Path) -> str:
    db = tmp_path / "fb.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _add(db: str, *, apply: bool, ftype: str = "needs_review", tid: str = "ol-1") -> dict:
    args = ["add", "--feedback-type", ftype, "--target-kind", "open_loop", "--target-id", tid,
            "--note", "please review", "--db", db, "--json"]
    args.append("--apply" if apply else "--dry-run")
    res = runner.invoke(app, args)
    assert res.exit_code == 0, res.output
    return json.loads(res.output)


def test_add_dry_run_default_persists_nothing(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = _add(db, apply=False)
    assert out["mode"] == "dry_run" and out["applied"] is False
    listed = runner.invoke(app, ["list", "--db", db, "--json"])
    assert json.loads(listed.output)["count"] == 0


def test_add_apply_persists_and_lists(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = _add(db, apply=True)
    assert out["mode"] == "apply" and out["applied"] is True
    fid = out["feedback"]["feedback_id"]
    listed = json.loads(runner.invoke(app, ["list", "--db", db, "--json"]).output)
    assert listed["count"] == 1
    shown = json.loads(runner.invoke(app, ["show", "--feedback-id", fid, "--db", db, "--json"]).output)
    assert shown["feedback"]["feedback_id"] == fid
    assert len(shown["targets"]) == 1


def test_recommendations_are_advisory(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _add(db, apply=True, ftype="wrong_source")
    recs = json.loads(runner.invoke(app, ["recommendations", "--db", db, "--json"]).output)
    assert recs["count"] >= 1
    assert all(r["review_policy"] == "advisory_review_loop" for r in recs["recommendations"])


def test_export_is_read_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    fid = _add(db, apply=True)["feedback"]["feedback_id"]
    exported = json.loads(
        runner.invoke(app, ["export", "--feedback-id", fid, "--db", db, "--json"]).output)
    assert exported["format"] == "feedback_export_v1"


def test_add_bad_type_exits_nonzero(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = runner.invoke(app, ["add", "--feedback-type", "accepted", "--target-kind", "open_loop",
                              "--target-id", "x", "--db", db, "--json", "--apply"])
    assert res.exit_code == 1
    assert "error" in res.output


def test_no_disposition_or_execution_commands() -> None:
    names = {c.name for c in app.registered_commands}
    assert names == {"add", "list", "show", "recommendations", "export"}
    for banned in ("accept", "reject", "defer", "dispose", "execute", "send", "schedule", "stage",
                   "remind", "apply"):
        assert banned not in names
