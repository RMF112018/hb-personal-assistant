"""N8C-19 action-stage repository: idempotent upsert, lineage-scoped supersede, writes ONLY the five
stage-owned tables, emits created/staged lifecycle events, never touches an upstream table."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import action_stage_models as M
from hb_assistant.obsidian_mcp.action_stage_models import ActionStageValidationError
from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository
from hb_assistant.store.migrator import SQLiteMigrator


def _db(tmp_path: Path) -> str:
    db = tmp_path / "as.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _stage(stage_id: str, *, request_digest: str = "req1", input_digest: str = "in1",
           status: str = "staged") -> dict:
    return {"stage_id": stage_id, "stage_type": "open_loop_actions", "workflow_type": "open_loop_triage",
            "workflow_id": "wf1", "status": status, **M.STAGE_POLICY_BLOCK, "created_by": "test",
            "request_digest": request_digest, "source_context_digest": "ctx", "input_digest": input_digest,
            "output_digest": "out", "stage_policy_json": "pol", "budget_json": "bud", "item_count": 1,
            "blocked_count": 0, "citation_count": 1}


def _item(stage_id: str) -> dict:
    return M.ActionStageItem(action_kind="open_loop_follow_up", target_kind="open_loop", target_id="OL1",
                             anchors={"open_loop_id": "OL1"}).to_row(stage_id, 0)


def _citation(stage_id: str, item_id: str) -> dict:
    return M.ActionStageCitation(stage_item_id=item_id, anchors={"open_loop_id": "OL1"}).to_row(stage_id, 0)


def _receipt(stage_id: str) -> dict:
    return {"stage_receipt_id": f"r-{stage_id}", "stage_id": stage_id, "builder_version": "v",
            "input_digest": "in1", "output_digest": "out", "item_count": 1, "citation_count": 1}


def _apply(repo: ActionStageRepository, stage: dict) -> dict:
    item = _item(stage["stage_id"])
    return repo.upsert_stage(stage, [item], [_citation(stage["stage_id"], item["stage_item_id"])],
                             _receipt(stage["stage_id"]))


def test_upsert_persists_all_five_tables(tmp_path: Path) -> None:
    repo = ActionStageRepository(_db(tmp_path))
    res = _apply(repo, _stage("S1"))
    assert res["created"] is True and res["reused"] is False
    assert repo.get_stage("S1") is not None
    assert len(repo.list_items("S1")) == 1
    assert len(repo.list_citations("S1")) == 1
    assert len(repo.list_receipts("S1")) == 1
    events = {e["event_type"] for e in repo.list_events("S1")}
    assert {"created", "staged"} <= events


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    repo = ActionStageRepository(_db(tmp_path))
    _apply(repo, _stage("S1"))
    again = _apply(repo, _stage("S1"))
    assert again["reused"] is True and again["created"] is False
    assert repo.count() == 1
    assert len(repo.list_items("S1")) == 1


def test_lineage_supersede(tmp_path: Path) -> None:
    # A new stage_id in the same (stage_type, workflow_type, request_digest, policy) lineage supersedes the
    # prior staged one — a stage-owned status change only.
    repo = ActionStageRepository(_db(tmp_path))
    _apply(repo, _stage("S1", request_digest="reqA", input_digest="inA"))
    res = _apply(repo, _stage("S2", request_digest="reqA", input_digest="inB"))
    assert "S1" in res["superseded"]
    assert repo.get_stage("S1")["status"] == "superseded"
    assert repo.get_stage("S2")["status"] == "staged"
    assert "superseded" in {e["event_type"] for e in repo.list_events("S1")}


def test_different_lineage_not_superseded(tmp_path: Path) -> None:
    repo = ActionStageRepository(_db(tmp_path))
    _apply(repo, _stage("S1", request_digest="reqA"))
    res = _apply(repo, _stage("S2", request_digest="reqB"))  # different request_digest
    assert res["superseded"] == []
    assert repo.get_stage("S1")["status"] == "staged"


def test_upsert_requires_stage_id_and_type(tmp_path: Path) -> None:
    repo = ActionStageRepository(_db(tmp_path))
    bad = _stage("S1")
    del bad["stage_type"]
    with pytest.raises(ActionStageValidationError):
        repo.upsert_stage(bad, [], [], _receipt("S1"))


def test_upsert_writes_only_stage_tables(tmp_path: Path) -> None:
    db = _db(tmp_path)
    repo = ActionStageRepository(db)
    with sqlite3.connect(db) as c:
        other = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'assistant_action_stage%' AND name NOT LIKE 'sqlite_%'")]
        before = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    _apply(repo, _stage("S1"))
    with sqlite3.connect(db) as c:
        after = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    assert before == after


def test_summary_and_filters(tmp_path: Path) -> None:
    repo = ActionStageRepository(_db(tmp_path))
    _apply(repo, _stage("S1", request_digest="reqA"))
    _apply(repo, _stage("S2", request_digest="reqB"))
    summary = repo.summary()
    assert summary["total_stages"] == 2
    assert summary["by_stage_type"].get("open_loop_actions") == 2
    assert len(repo.list_stages(status="staged")) == 2


def test_persisted_items_are_non_executing(tmp_path: Path) -> None:
    repo = ActionStageRepository(_db(tmp_path))
    _apply(repo, _stage("S1"))
    for it in repo.list_items("S1"):
        assert it["execution_status"] == "not_executed"
        assert it["external_system"] == "none"
        assert it["external_ref"] is None
        assert it["requires_operator_review"] == 1
