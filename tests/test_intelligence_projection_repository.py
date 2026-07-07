"""N8C-10 projection repository + models: deterministic ids, idempotent upsert, lineage supersede
(projection-owned only), inclusion classification, and budget policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.intelligence_projection_models import (
    CANDIDATE_CONTEXT,
    IMPLEMENTATION_CONTEXT,
    REVIEW_AWARE_CONTEXT,
    TRUSTED_CONTEXT,
    ProjectionBudget,
    ProjectionItem,
    ProjectionValidationError,
    classify_inclusion_state,
    compute_projection_id,
    compute_projection_item_id,
    compute_projection_receipt_id,
)
from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
    IntelligenceProjectionRepository,
)
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> IntelligenceProjectionRepository:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return IntelligenceProjectionRepository(db)


def _header(pid: str, ptype: str = TRUSTED_CONTEXT, scope: str = '{"pack_id":"p1"}',
            input_digest: str = "in1") -> dict:
    return {"projection_id": pid, "projection_type": ptype, "scope_json": scope,
            "filter_policy_json": "{}", "budget_json": "{}", "status": "built",
            "input_digest": input_digest, "output_digest": "out1", "item_count": 1,
            "trusted_count": 1, "created_by": "test"}


def _item(pid: str, target_id: str = "c1") -> dict:
    return ProjectionItem(target_kind="claim", target_id=target_id, inclusion_state="trusted",
                          included=True, review_item_id="r1", effective_state="accepted",
                          target_digest="d1", claim_id=target_id, summary="s").to_row(pid)


def _receipt(pid: str, input_digest: str = "in1") -> dict:
    return {"projection_receipt_id": compute_projection_receipt_id(pid, input_digest, "out1"),
            "projection_id": pid, "builder_version": "intel-projection-v1", "input_digest": input_digest,
            "output_digest": "out1", "trusted_count": 1}


# ---- deterministic identity ----
def test_ids_deterministic() -> None:
    a = compute_projection_id("trusted_context", "s", "p", "b", "in1")
    assert a == compute_projection_id("trusted_context", "s", "p", "b", "in1")
    assert a != compute_projection_id("trusted_context", "s", "p", "b", "in2")  # changed input_digest
    i = compute_projection_item_id(a, "claim", "c1", "r1", "accepted", "d1")
    assert i == compute_projection_item_id(a, "claim", "c1", "r1", "accepted", "d1")
    assert i != compute_projection_item_id(a, "claim", "c1", "r1", "rejected", "d1")  # eff state folds in
    assert compute_projection_receipt_id(a, "in1", "out1") == compute_projection_receipt_id(a, "in1", "out1")


# ---- inclusion classification ----
def test_classification_by_effective_state() -> None:
    trusted = ProjectionBudget.for_type(TRUSTED_CONTEXT)
    review = ProjectionBudget.for_type(REVIEW_AWARE_CONTEXT)
    assert classify_inclusion_state("accepted", trusted) == ("trusted", True)
    assert classify_inclusion_state("rejected", trusted) == ("excluded", False)
    assert classify_inclusion_state("not_required", trusted) == ("not_required", False)
    assert classify_inclusion_state("superseded", trusted) == ("superseded", False)
    assert classify_inclusion_state("stale", trusted) == ("stale", False)
    assert classify_inclusion_state("deferred", trusted) == ("deferred", False)
    # candidate excluded in trusted_context, included (labeled) in review_aware_context
    assert classify_inclusion_state("candidate", trusted) == ("candidate", False)
    assert classify_inclusion_state("candidate", review) == ("candidate", True)


def test_policy_defaults() -> None:
    assert ProjectionBudget.for_type(TRUSTED_CONTEXT).include_candidates is False
    assert ProjectionBudget.for_type(REVIEW_AWARE_CONTEXT).include_candidates is True
    assert ProjectionBudget.for_type(CANDIDATE_CONTEXT).include_candidates is True
    impl = ProjectionBudget.for_type(IMPLEMENTATION_CONTEXT)
    assert impl.include_candidates is True and impl.include_stale is False
    assert impl.include_open_loops is True  # advisory only


# ---- item validation ----
def test_item_requires_provenance() -> None:
    with pytest.raises(ProjectionValidationError):
        ProjectionItem(target_kind="claim", target_id="c1", inclusion_state="trusted",
                       included=True).to_row("p1")


def test_item_rejects_unknown_inclusion_state() -> None:
    with pytest.raises(ProjectionValidationError):
        ProjectionItem(target_kind="claim", target_id="c1", inclusion_state="bogus", included=True,
                       claim_id="c1").to_row("p1")


# ---- upsert / idempotency / supersede ----
def test_upsert_idempotent(repo: IntelligenceProjectionRepository) -> None:
    pid = "proj1"
    r1 = repo.upsert_projection(_header(pid), [_item(pid)], _receipt(pid))
    assert r1["created"] is True
    r2 = repo.upsert_projection(_header(pid), [_item(pid)], _receipt(pid))
    assert r2["reused"] is True and r2["created"] is False
    assert repo.count() == 1
    assert len(repo.list_projection_items(pid)) == 1


def test_changed_input_supersedes_prior_same_type_scope(repo: IntelligenceProjectionRepository) -> None:
    p1 = "projA"
    p2 = "projB"
    repo.upsert_projection(_header(p1, input_digest="in1"), [_item(p1)], _receipt(p1, "in1"))
    res = repo.upsert_projection(_header(p2, input_digest="in2"), [_item(p2)], _receipt(p2, "in2"))
    assert res["created"] is True and res["superseded"] == [p1]
    assert repo.get_projection(p1)["status"] == "superseded"
    assert repo.get_projection(p2)["status"] == "built"


def test_independent_scope_coexists(repo: IntelligenceProjectionRepository) -> None:
    repo.upsert_projection(_header("x", scope='{"pack_id":"p1"}'), [_item("x")], _receipt("x"))
    repo.upsert_projection(_header("y", scope='{"pack_id":"p2"}'), [_item("y")], _receipt("y"))
    assert repo.count() == 2  # different scope lineages never supersede each other


def test_mark_stale_if_needed(repo: IntelligenceProjectionRepository) -> None:
    pid = "projS"
    repo.upsert_projection(_header(pid, input_digest="in1"), [_item(pid)], _receipt(pid, "in1"))
    res = repo.mark_projection_stale_if_needed(pid, current_input_digest="in-DIFFERENT")
    assert res["stale"] is True
    assert repo.get_projection(pid)["status"] == "stale"


def test_summary_shape(repo: IntelligenceProjectionRepository) -> None:
    repo.upsert_projection(_header("s1"), [_item("s1")], _receipt("s1"))
    s = repo.summary()
    assert s["total_projections"] == 1 and s["total_items"] == 1
    assert "by_projection_type" in s and "by_status" in s
