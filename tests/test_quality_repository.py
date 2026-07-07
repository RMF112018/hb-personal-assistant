"""N8C-20 quality repository: idempotent upsert, lineage-scoped supersede, writes ONLY the five quality-owned
tables, emits created/evaluated lifecycle events, never touches an upstream table."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import quality_models as M
from hb_assistant.obsidian_mcp.quality_models import QualityValidationError
from hb_assistant.obsidian_mcp.quality_repository import QualityRepository
from hb_assistant.store.migrator import SQLiteMigrator


def _db(tmp_path: Path) -> str:
    db = tmp_path / "q.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _run(rid: str, *, target_id: str = "f1", input_digest: str = "in1",
         policy_json: str = "pol") -> dict:
    return {"quality_run_id": rid, "target_kind": "feedback", "target_id": target_id,
            "target_digest": input_digest, "title": "t", "status": "evaluated", **M.QUALITY_POLICY_BLOCK,
            "evaluator_version": "quality-v1", "created_by": "test", "request_digest": "req1",
            "input_digest": input_digest, "output_digest": "out", "policy_json": policy_json,
            "finding_count": 1, "risk_count": 0, "warn_count": 1, "info_count": 0, "truncated": 0}


def _finding(rid: str) -> dict:
    return M.QualityFinding(finding_type="missing_citation", severity="warn", target_kind="feedback",
                            target_id="f1", detail="d").to_row(rid, 0)


def _target(rid: str) -> dict:
    return M.QualityTarget(target_kind="feedback", target_id="f1").to_row(rid, 0)


def _receipt(rid: str) -> dict:
    return {"quality_receipt_id": f"r-{rid}", "quality_run_id": rid, "evaluator_version": "quality-v1",
            "request_digest": "req1", "input_digest": "in1", "output_digest": "out", "finding_count": 1}


def _apply(repo: QualityRepository, run: dict) -> dict:
    rid = run["quality_run_id"]
    return repo.upsert_quality_run(run, [_finding(rid)], [_target(rid)], _receipt(rid))


def test_upsert_persists_all_five_tables(tmp_path: Path) -> None:
    repo = QualityRepository(_db(tmp_path))
    res = _apply(repo, _run("R1"))
    assert res["created"] is True and res["reused"] is False
    assert repo.get_quality_run("R1") is not None
    assert len(repo.list_findings("R1")) == 1
    assert len(repo.list_targets("R1")) == 1
    assert len(repo.list_receipts("R1")) == 1
    events = {e["event_type"] for e in repo.list_events("R1")}
    assert {"created", "evaluated"} <= events


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    repo = QualityRepository(_db(tmp_path))
    _apply(repo, _run("R1"))
    again = _apply(repo, _run("R1"))
    assert again["reused"] is True and again["created"] is False
    assert repo.count() == 1
    assert len(repo.list_findings("R1")) == 1


def test_lineage_supersede(tmp_path: Path) -> None:
    # A new run id in the same (target_kind, target_id, policy_json) lineage supersedes the prior evaluated
    # one — a quality-owned status change only.
    repo = QualityRepository(_db(tmp_path))
    _apply(repo, _run("R1", input_digest="inA", policy_json="polA"))
    res = _apply(repo, _run("R2", input_digest="inB", policy_json="polA"))
    assert "R1" in res["superseded"]
    assert repo.get_quality_run("R1")["status"] == "superseded"
    assert repo.get_quality_run("R2")["status"] == "evaluated"
    assert "superseded" in {e["event_type"] for e in repo.list_events("R1")}


def test_different_lineage_not_superseded(tmp_path: Path) -> None:
    repo = QualityRepository(_db(tmp_path))
    _apply(repo, _run("R1", policy_json="polA"))
    res = _apply(repo, _run("R2", policy_json="polB"))  # different policy_json → different lineage
    assert res["superseded"] == []
    assert repo.get_quality_run("R1")["status"] == "evaluated"


def test_upsert_requires_ids(tmp_path: Path) -> None:
    repo = QualityRepository(_db(tmp_path))
    bad = _run("R1")
    del bad["target_kind"]
    with pytest.raises(QualityValidationError):
        repo.upsert_quality_run(bad, [], [], _receipt("R1"))


def test_upsert_writes_only_quality_tables(tmp_path: Path) -> None:
    db = _db(tmp_path)
    repo = QualityRepository(db)
    with sqlite3.connect(db) as c:
        other = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'assistant_quality%' AND name NOT LIKE 'sqlite_%'")]
        before = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    _apply(repo, _run("R1"))
    with sqlite3.connect(db) as c:
        after = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in other}
    assert before == after


def test_summary_and_filters(tmp_path: Path) -> None:
    repo = QualityRepository(_db(tmp_path))
    _apply(repo, _run("R1", policy_json="polA"))
    _apply(repo, _run("R2", policy_json="polB"))
    summary = repo.summary()
    assert summary["total_runs"] == 2
    assert summary["by_target_kind"].get("feedback") == 2
    assert summary["by_finding_type"].get("missing_citation") == 2
    assert len(repo.list_quality_runs(status="evaluated")) == 2


def test_invalid_event_type_rejected(tmp_path: Path) -> None:
    repo = QualityRepository(_db(tmp_path))
    db = repo.db_path
    with sqlite3.connect(db) as c, pytest.raises(QualityValidationError):
        repo._insert_event(c, "R1", "repaired", from_status=None, to_status=None, detail=None,
                           now="2026-01-01")
