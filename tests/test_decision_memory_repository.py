"""N8C-8 decision-memory repository: determinism, idempotency, lineage-scoped supersede, provenance."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import decision_memory_models as M
from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> DecisionMemoryRepository:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return DecisionMemoryRepository(db)


def _decision(*, source_id="s1", claim_id="c1", evidence="we decided X", digest="sd1",
              subject="mcp", decision="keep read-only") -> dict:
    return M.DecisionRecord(
        decision_type="decision_candidate", decision_text="decided X", normalized_subject=subject,
        normalized_decision=decision, source_id=source_id, claim_id=claim_id,
        evidence_excerpt=evidence, source_digest=digest, confidence=0.8).to_row()


def test_decision_id_determinism() -> None:
    a = _decision()["decision_id"]
    b = _decision()["decision_id"]
    assert a == b


def test_preference_and_open_loop_id_determinism() -> None:
    p = lambda: M.PreferenceRecord(preference_type="user_preference", normalized_subject="commits",
                                   normalized_preference="no ai trailer", domain="git",
                                   source_id="s1", claim_id="c2", evidence_excerpt="prefer",
                                   source_digest="d").to_row()["preference_id"]
    ol = lambda: M.OpenLoopRecord(open_loop_type="commitment", normalized_subject="sched",
                                  normalized_action="send", source_id="s1", claim_id="c3",
                                  evidence_excerpt="will send", source_digest="d").to_row()["open_loop_id"]
    assert p() == p()
    assert ol() == ol()


def test_upsert_idempotent_no_duplicate(repo) -> None:
    row = _decision()
    assert repo.upsert_decision(row)["created"] is True
    assert repo.upsert_decision(row)["reused"] is True
    assert repo.count("decision") == 1


def test_changed_evidence_supersedes_same_lineage(repo) -> None:
    repo.upsert_decision(_decision(evidence="v1", digest="d1"))
    res = repo.upsert_decision(_decision(evidence="v2 updated", digest="d2"))
    assert res["created"] is True
    assert len(res["superseded"]) == 1  # prior candidate of the same lineage superseded
    statuses = sorted(r["status"] for r in repo.list_decisions())
    assert statuses == ["candidate", "superseded"]


def test_independent_sources_coexist(repo) -> None:
    # Same subject+decision, DIFFERENT source lineage → different identity_key → no supersede.
    repo.upsert_decision(_decision(source_id="s1", claim_id="c1", evidence="a", digest="d1"))
    res = repo.upsert_decision(_decision(source_id="s2", claim_id="c2", evidence="b", digest="d2"))
    assert res["superseded"] == []
    active = [r for r in repo.list_decisions() if r["status"] == "candidate"]
    assert len(active) == 2  # corroborating sources coexist, never auto-obsolete


def test_record_requires_provenance() -> None:
    with pytest.raises(M.DecisionMemoryValidationError, match="provenance"):
        M.DecisionRecord(decision_type="decision", decision_text="x").to_row()


def test_anchor_key_falls_back_when_source_absent() -> None:
    # No source_id, but a claim_id → identity_key still stable (anchor_key precedence).
    a = M.DecisionRecord(decision_type="decision", normalized_subject="s", normalized_decision="d",
                         claim_id="c9", evidence_excerpt="e").to_row()
    b = M.DecisionRecord(decision_type="decision", normalized_subject="s", normalized_decision="d",
                         claim_id="c9", evidence_excerpt="e").to_row()
    assert a["identity_key"] == b["identity_key"]
    assert a["decision_id"] == b["decision_id"]


def test_default_status_and_review_state() -> None:
    row = _decision()
    assert row["status"] == "candidate"
    assert row["review_state"] == "unreviewed"


def test_mark_open_loop_stale(repo) -> None:
    ol = M.OpenLoopRecord(open_loop_type="commitment", normalized_subject="sched",
                          normalized_action="send", source_id="s1", claim_id="c3",
                          evidence_excerpt="will send").to_row()
    repo.upsert_open_loop(ol)
    assert repo.mark_open_loop_stale(ol["open_loop_id"], detail="drift") is True
    assert repo.get_open_loop(ol["open_loop_id"])["status"] == "stale"
    assert "marked_stale" in [e["event_type"] for e in repo.list_events(ol["open_loop_id"])]
    assert repo.mark_open_loop_stale("nope") is False


def test_created_event_logged(repo) -> None:
    row = _decision()
    repo.upsert_decision(row)
    events = repo.list_events(row["decision_id"])
    assert [e["event_type"] for e in events] == ["created"]
    assert events[0]["record_kind"] == "decision"


def test_list_decisions_filters_by_bounded_query(repo) -> None:
    repo.upsert_decision(_decision(subject="budget", decision="freeze scope"))
    repo.upsert_decision(_decision(subject="scheduling", decision="send update", source_id="s2", claim_id="c2"))
    matches = repo.list_decisions(query="budget")
    assert len(matches) == 1
    assert matches[0]["normalized_subject"] == "budget"
    assert repo.list_decisions(query="missing-topic") == []
