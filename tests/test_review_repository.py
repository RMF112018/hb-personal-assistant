"""N8C-9 review repository: id determinism, idempotency, lineage supersede, append-only dispositions,
computed effective state, and source-table nonmutation."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.review_disposition import apply_disposition, preview_disposition
from hb_assistant.obsidian_mcp.review_models import (
    ReviewItem,
    ReviewValidationError,
    compute_review_item_id,
)
from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> ReviewRepository:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return ReviewRepository(db)


def _item(target_id: str = "c1", target_digest: str = "d1", **kw) -> dict:
    return ReviewItem(target_kind="claim", target_id=target_id, review_type="claim_review",
                      target_digest=target_digest, claim_id=target_id, summary="s",
                      evidence_excerpt="ev", **kw).to_row()


def test_review_item_id_deterministic() -> None:
    a = compute_review_item_id("claim", "c1", "d1", "claim_review")
    b = compute_review_item_id("claim", "c1", "d1", "claim_review")
    assert a == b == _item()["review_item_id"]
    assert compute_review_item_id("claim", "c1", "d2", "claim_review") != a


def test_default_state_is_unreviewed_candidate() -> None:
    row = _item()
    assert row["review_state"] == "unreviewed"
    assert row["effective_state"] == "candidate"


def test_item_without_provenance_rejected() -> None:
    with pytest.raises(ReviewValidationError):
        ReviewItem(target_kind="claim", target_id="c1", review_type="claim_review").to_row()


def test_upsert_idempotent(repo: ReviewRepository) -> None:
    row = _item()
    assert repo.upsert_review_item(row)["created"] is True
    r2 = repo.upsert_review_item(row)
    assert r2["reused"] is True and r2["created"] is False
    assert repo.count() == 1


def test_changed_digest_supersedes_prior_same_lineage(repo: ReviewRepository) -> None:
    r1 = repo.upsert_review_item(_item(target_digest="d1"))
    r2 = repo.upsert_review_item(_item(target_digest="d2"))
    assert r2["created"] is True
    assert r2["superseded"] == [r1["review_item_id"]]
    prior = repo.get_review_item(r1["review_item_id"])
    assert prior["superseded"] == 1 and prior["review_state"] == "superseded"
    # active listing excludes the superseded prior
    active = repo.list_review_items()
    assert [i["review_item_id"] for i in active] == [r2["review_item_id"]]


def test_independent_targets_coexist(repo: ReviewRepository) -> None:
    repo.upsert_review_item(_item(target_id="c1"))
    repo.upsert_review_item(_item(target_id="c2"))
    assert repo.count() == 2  # different target lineages never supersede each other


def test_disposition_maps(repo: ReviewRepository) -> None:
    cases = {
        "accept": ("operator_accepted", "accepted"),
        "reject": ("operator_rejected", "rejected"),
        "defer": ("deferred", "deferred"),
        "mark_not_required": ("not_required", "not_required"),
        "request_more_context": ("needs_review", "candidate"),
    }
    for i, (dtype, (rstate, estate)) in enumerate(cases.items()):
        rid = repo.upsert_review_item(_item(target_id=f"c{i}"))["review_item_id"]
        res = repo.record_disposition(review_item_id=rid, disposition_type=dtype)
        assert (res["to_review_state"], res["to_effective_state"]) == (rstate, estate)
        eff = repo.get_effective_state(rid)
        assert (eff["effective_review_state"], eff["effective_state"]) == (rstate, estate)


def test_dispositions_are_append_only(repo: ReviewRepository) -> None:
    rid = repo.upsert_review_item(_item())["review_item_id"]
    d1 = repo.record_disposition(review_item_id=rid, disposition_type="accept", reason="ok")
    d2 = repo.record_disposition(review_item_id=rid, disposition_type="defer", reason="hold")
    assert d1["disposition_id"] != d2["disposition_id"]
    assert len(repo.list_dispositions(rid)) == 2
    # latest disposition (defer) determines effective state
    eff = repo.get_effective_state(rid)
    assert eff["effective_state"] == "deferred" and eff["disposed"] is True


def test_disposition_does_not_mutate_item_columns(repo: ReviewRepository) -> None:
    rid = repo.upsert_review_item(_item())["review_item_id"]
    repo.record_disposition(review_item_id=rid, disposition_type="accept")
    item = repo.get_review_item(rid)
    # overlay: the item's built columns are untouched; effective state is computed, not written back
    assert item["review_state"] == "unreviewed" and item["effective_state"] == "candidate"


def test_disposition_on_missing_item_raises(repo: ReviewRepository) -> None:
    with pytest.raises(ReviewValidationError):
        repo.record_disposition(review_item_id="nope", disposition_type="accept")


def test_disposition_preview_is_read_only(repo: ReviewRepository) -> None:
    rid = repo.upsert_review_item(_item())["review_item_id"]
    pv = preview_disposition(repo, review_item_id=rid, disposition_type="accept")
    assert pv["applied"] is False and pv["to_effective_state"] == "accepted"
    assert len(repo.list_dispositions(rid)) == 0  # nothing written
    # apply=False path of the service also writes nothing
    apply_disposition(repo, review_item_id=rid, disposition_type="accept", apply=False)
    assert len(repo.list_dispositions(rid)) == 0


def test_effective_state_for_target(repo: ReviewRepository) -> None:
    rid = repo.upsert_review_item(_item(target_id="cX"))["review_item_id"]
    repo.record_disposition(review_item_id=rid, disposition_type="reject")
    states = repo.effective_state_for_target("claim", "cX")
    assert len(states) == 1 and states[0]["effective_state"] == "rejected"
