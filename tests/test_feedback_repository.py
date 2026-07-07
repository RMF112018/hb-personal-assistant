"""N8C-18 feedback repository: idempotent upsert, writes ONLY the five feedback-owned tables, requires ≥1
provenance target, emits the created/linked/recommended lifecycle events, and never touches an upstream
(workflow / review / source / draft / packet / projection / context-pack / open-loop) table."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_models import FeedbackValidationError
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.store.migrator import SQLiteMigrator


def _db(tmp_path: Path) -> str:
    db = tmp_path / "fb.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _plan(feedback_type: str = "needs_review", tid: str = "ol-1") -> dict:
    return fs.preview_feedback(
        feedback_type=feedback_type,
        targets=[{"target_kind": "open_loop", "target_id": tid, "open_loop_id": tid}],
        note="please look", created_by="test")


def _apply(repo: FeedbackRepository, plan: dict) -> dict:
    return repo.upsert_feedback(plan["feedback"], plan["targets"], plan["recommendations"],
                                plan["receipt"])


def test_upsert_persists_all_five_tables(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    plan = _plan()
    res = _apply(repo, plan)
    assert res["created"] is True and res["reused"] is False
    fid = plan["feedback"]["feedback_id"]
    assert repo.get_feedback(fid) is not None
    assert len(repo.list_targets(fid)) == 1
    assert len(repo.list_recommendations(fid)) == 1
    assert len(repo.list_receipts(fid)) == 1
    events = {e["event_type"] for e in repo.list_events(fid)}
    assert {"created", "linked", "recommended"} <= events


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    plan = _plan()
    _apply(repo, plan)
    again = _apply(repo, plan)
    assert again["reused"] is True and again["created"] is False
    assert repo.count() == 1
    assert len(repo.list_targets(plan["feedback"]["feedback_id"])) == 1  # no duplicate rows


def test_upsert_requires_at_least_one_target(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    plan = _plan()
    with pytest.raises(FeedbackValidationError):
        repo.upsert_feedback(plan["feedback"], [], plan["recommendations"], plan["receipt"])


def test_upsert_writes_only_feedback_tables(tmp_path: Path) -> None:
    # Snapshot every non-feedback table's rowcount before/after apply — none may change.
    db = _db(tmp_path)
    repo = FeedbackRepository(db)
    with sqlite3.connect(db) as c:
        other = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'assistant_feedback%' AND name NOT LIKE 'sqlite_%'")]
        before = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    _apply(repo, _plan())
    with sqlite3.connect(db) as c:
        after = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    assert before == after


def test_useful_feedback_has_no_recommendation(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    plan = _plan(feedback_type="useful")
    _apply(repo, plan)
    fid = plan["feedback"]["feedback_id"]
    assert repo.list_recommendations(fid) == []
    # A record with no recommendation emits no 'recommended' event.
    assert "recommended" not in {e["event_type"] for e in repo.list_events(fid)}


def test_summary_and_list_filters(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    _apply(repo, _plan(feedback_type="needs_review", tid="a"))
    _apply(repo, _plan(feedback_type="duplicate", tid="b"))
    summary = repo.summary()
    assert summary["total_feedback"] == 2
    assert summary["by_feedback_type"].get("needs_review") == 1
    assert len(repo.list_feedback(feedback_type="duplicate")) == 1


def test_persisted_record_pins_fixed_policy(tmp_path: Path) -> None:
    repo = FeedbackRepository(_db(tmp_path))
    plan = _plan()
    _apply(repo, plan)
    rec = repo.get_feedback(plan["feedback"]["feedback_id"])
    assert rec["action_policy"] == "no_execution"
    assert rec["execution_policy"] == "feedback_only"
    assert rec["review_policy"] == "advisory_review_loop"
    assert rec["requires_operator_review"] == 1
    assert rec["status"] == "open"
