"""N8C-15 `hb-assistant workflow` CLI: read-only catalog + route (no --apply/--build/--execute flag)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.workflow import app
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "wf.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_catalog_is_read_only_and_lists_types() -> None:
    res = runner.invoke(app, ["catalog", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert len(payload["workflow_types"]) == 11
    assert payload["router_version"] == "workflow-router-v1"


def test_route_source_lookup(tmp_path: Path) -> None:
    res = runner.invoke(app, ["route", "--workflow-type", "source_file_lookup",
                              "--query", "invoice pdf", "--db", _db(tmp_path), "--json"])
    assert res.exit_code == 0
    env = json.loads(res.stdout)
    assert env["workflow_type"] == "source_file_lookup"
    assert env["status"] == "routed"
    assert env["action_policy"] == "no_execution"


def test_route_missing_artifact(tmp_path: Path) -> None:
    res = runner.invoke(app, ["route", "--workflow-type", "research_answer",
                              "--draft-id", "NOPE", "--db", _db(tmp_path), "--json"])
    env = json.loads(res.stdout)
    assert env["status"] == "missing_required_artifact"


def test_route_action_draft_preparation_deferred(tmp_path: Path) -> None:
    res = runner.invoke(app, ["route", "--workflow-type", "action_draft_preparation",
                              "--db", _db(tmp_path), "--json"])
    env = json.loads(res.stdout)
    assert env["status"] == "deferred"
    assert env["deferred_capabilities"]


def test_no_apply_or_build_flag() -> None:
    # The route command must expose no execution/build/apply flag.
    help_txt = runner.invoke(app, ["route", "--help"]).stdout
    for flag in ("--apply", "--build", "--execute", "--send", "--schedule"):
        assert flag not in help_txt


def test_route_draft_review_flags_warnings(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_answer_drafts (draft_id, draft_type, status, citation_count) "
                  "VALUES (?,?,?,?)", ("D9", "review_aware_answer_draft", "built", 0))
    res = runner.invoke(app, ["route", "--workflow-type", "draft_review", "--draft-id", "D9",
                              "--db", db, "--json"])
    env = json.loads(res.stdout)
    assert "draft_has_no_citations" in env["warnings"]
