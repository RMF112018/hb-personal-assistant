"""N8C-11 packet repository + models: deterministic ids (packet/item/citation/receipt), citation-id anchor
entropy (no collisions), idempotent upsert, lineage supersede (packet-owned only), computed answer_allowed,
and dual-layer provenance validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.research_packet_models import (
    REVIEW_AWARE_ANSWER_CONTEXT,
    TRUSTED_ANSWER_CONTEXT,
    Citation,
    PacketBudget,
    ResearchPacketItem,
    ResearchPacketValidationError,
    build_answer_contract,
    classify_answer_role,
    compute_citation_id,
    compute_packet_id,
    compute_packet_item_id,
    compute_packet_receipt_id,
)
from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> ResearchPacketRepository:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return ResearchPacketRepository(db)


def _header(pid: str, ptype: str = TRUSTED_ANSWER_CONTEXT, projection: str = "proj1",
            input_digest: str = "in1") -> dict:
    return {"packet_id": pid, "packet_type": ptype, "projection_id": projection, "scope_json": "{}",
            "answer_contract_json": "{}", "budget_json": "{}", "status": "built",
            "input_digest": input_digest, "output_digest": "out1", "answer_contract_digest": "ac1",
            "item_count": 1, "trusted_count": 1, "citation_count": 1, "created_by": "test"}


def _item(pid: str, target_id: str = "c1") -> dict:
    return ResearchPacketItem(packet_id=pid, answer_role="primary_support", included=True,
                              target_kind="claim", target_id=target_id, claim_id=target_id,
                              projection_item_id="pit1", effective_state="accepted",
                              inclusion_state="trusted", summary="s").to_row()


def _citation(pid: str, item_id: str) -> dict:
    return Citation(packet_id=pid, packet_item_id=item_id, citation_type="claim", citation_order=0,
                    anchor_kind="claim_id", anchor_id="c1", claim_id="c1", target_kind="claim",
                    target_id="c1").to_row()


def _receipt(pid: str, input_digest: str = "in1") -> dict:
    return {"packet_receipt_id": compute_packet_receipt_id(pid, input_digest, "out1", "ac1"),
            "packet_id": pid, "builder_version": "research-packet-v1", "input_digest": input_digest,
            "output_digest": "out1", "answer_contract_digest": "ac1", "trusted_count": 1,
            "citation_count": 1}


# ---- deterministic identity ----
def test_ids_deterministic() -> None:
    a = compute_packet_id("t", "p", "obj", "q", "{}", "{}", "in1")
    assert a == compute_packet_id("t", "p", "obj", "q", "{}", "{}", "in1")
    assert a != compute_packet_id("t", "p", "obj", "q", "{}", "{}", "in2")  # changed input_digest
    i = compute_packet_item_id(a, "pit1", "primary_support", "accepted", "d1")
    assert i == compute_packet_item_id(a, "pit1", "primary_support", "accepted", "d1")
    assert i != compute_packet_item_id(a, "pit1", "candidate_context", "accepted", "d1")  # role folds in
    assert compute_packet_receipt_id(a, "in1", "out1", "ac1") == compute_packet_receipt_id(a, "in1",
                                                                                           "out1", "ac1")


def test_citation_id_anchor_entropy_no_collision() -> None:
    # Same target + digest but different anchor / order must produce distinct citation ids.
    base = {"packet_id": "p", "packet_item_id": "i", "citation_type": "source", "target_kind": "claim",
            "target_id": "t", "source_digest": "sd", "target_digest": "td"}
    c1 = compute_citation_id(**base, anchor_kind="source_id", anchor_id="s1", citation_order=0)
    c2 = compute_citation_id(**base, anchor_kind="note_rel_path", anchor_id="n1", citation_order=1)
    c3 = compute_citation_id(**base, anchor_kind="source_id", anchor_id="s1", citation_order=0)
    assert c1 != c2  # different anchor + order → no collision
    assert c1 == c3  # fully identical → stable


# ---- answer-role classification ----
def test_classify_answer_role() -> None:
    trusted = PacketBudget.for_type(TRUSTED_ANSWER_CONTEXT)
    review = PacketBudget.for_type(REVIEW_AWARE_ANSWER_CONTEXT)
    assert classify_answer_role("trusted", TRUSTED_ANSWER_CONTEXT, trusted) == ("primary_support", True)
    assert classify_answer_role("candidate", TRUSTED_ANSWER_CONTEXT, trusted) == ("candidate_context", False)
    assert classify_answer_role("candidate", REVIEW_AWARE_ANSWER_CONTEXT, review) == ("candidate_context",
                                                                                      True)
    assert classify_answer_role("excluded", TRUSTED_ANSWER_CONTEXT, trusted) == ("excluded_context", False)
    assert classify_answer_role("superseded", TRUSTED_ANSWER_CONTEXT, trusted) == ("excluded_context", False)
    assert classify_answer_role("not_required", TRUSTED_ANSWER_CONTEXT, trusted) == ("excluded_context",
                                                                                     False)
    assert classify_answer_role("stale", TRUSTED_ANSWER_CONTEXT, trusted) == ("risk_or_caveat", False)
    assert classify_answer_role("deferred", TRUSTED_ANSWER_CONTEXT, trusted) == ("open_question", False)
    # implementation context relabels an open-loop trusted item as an advisory implementation note
    impl = PacketBudget.for_type("implementation_research_context")
    assert classify_answer_role("trusted", "implementation_research_context", impl,
                                target_kind="open_loop") == ("implementation_note", True)


# ---- answer contract (computed answer_allowed) ----
def test_answer_contract_answer_allowed_computed() -> None:
    b = PacketBudget.for_type(REVIEW_AWARE_ANSWER_CONTEXT)
    # only excluded support → not allowed
    c0 = build_answer_contract(REVIEW_AWARE_ANSWER_CONTEXT, b, trusted_included=0, candidate_included=0,
                               unresolved_questions=[], must_not_say=[])
    assert c0["answer_allowed"] is False
    assert c0["citation_required"] is True and c0["action_policy"] == "no_execution"
    assert c0["review_labels_required"] is True
    # trusted support present → allowed
    c1 = build_answer_contract(REVIEW_AWARE_ANSWER_CONTEXT, b, trusted_included=2, candidate_included=0,
                               unresolved_questions=[], must_not_say=[])
    assert c1["answer_allowed"] is True and c1["trusted_claims_allowed"] is True
    # only candidate support → allowed with caveat
    c2 = build_answer_contract(REVIEW_AWARE_ANSWER_CONTEXT, b, trusted_included=0, candidate_included=3,
                               unresolved_questions=["q?"], must_not_say=[{"target_id": "x"}])
    assert c2["answer_allowed"] is True and c2["candidate_claims_allowed"] == "with_caveat"
    assert c2["unresolved_questions"] == ["q?"] and c2["must_not_say"] == [{"target_id": "x"}]
    # trusted_answer_context with candidates only → candidates not allowed → not allowed
    tb = PacketBudget.for_type(TRUSTED_ANSWER_CONTEXT)
    c3 = build_answer_contract(TRUSTED_ANSWER_CONTEXT, tb, trusted_included=0, candidate_included=5,
                               unresolved_questions=[], must_not_say=[])
    assert c3["answer_allowed"] is False and c3["candidate_claims_allowed"] is False


def test_policy_defaults() -> None:
    assert PacketBudget.for_type(TRUSTED_ANSWER_CONTEXT).include_candidates is False
    assert PacketBudget.for_type(REVIEW_AWARE_ANSWER_CONTEXT).include_candidates is True
    impl = PacketBudget.for_type("implementation_research_context")
    assert impl.include_candidates is True and impl.include_stale is False


# ---- item / citation validation ----
def test_item_requires_provenance() -> None:
    with pytest.raises(ResearchPacketValidationError):
        ResearchPacketItem(packet_id="p", answer_role="primary_support", included=True,
                           target_kind="claim", target_id="c1").to_row()


def test_item_rejects_unknown_answer_role() -> None:
    with pytest.raises(ResearchPacketValidationError):
        ResearchPacketItem(packet_id="p", answer_role="bogus", included=True, target_kind="claim",
                           target_id="c1", claim_id="c1").to_row()


def test_citation_requires_provenance() -> None:
    with pytest.raises(ResearchPacketValidationError):
        Citation(packet_id="p", packet_item_id="i", citation_type="source", citation_order=0,
                 anchor_kind="none", anchor_id="").to_row()


def test_citation_projection_item_anchor_ok() -> None:
    row = Citation(packet_id="p", packet_item_id="i", citation_type="projection_item", citation_order=0,
                   anchor_kind="projection_item_id", anchor_id="pit1", projection_item_id="pit1").to_row()
    assert row["citation_id"] and row["projection_item_id"] == "pit1"


# ---- upsert / idempotency / supersede ----
def test_upsert_idempotent(repo: ResearchPacketRepository) -> None:
    pid = "pk1"
    item = _item(pid)
    r1 = repo.upsert_packet(_header(pid), [item], [_citation(pid, item["packet_item_id"])], _receipt(pid))
    assert r1["created"] is True
    r2 = repo.upsert_packet(_header(pid), [item], [_citation(pid, item["packet_item_id"])], _receipt(pid))
    assert r2["reused"] is True and r2["created"] is False
    assert repo.count() == 1
    assert len(repo.list_research_packet_items(pid)) == 1
    assert len(repo.list_research_packet_citations(pid)) == 1


def test_changed_input_supersedes_prior_same_lineage(repo: ResearchPacketRepository) -> None:
    p1, p2 = "pkA", "pkB"
    i1, i2 = _item(p1), _item(p2)
    repo.upsert_packet(_header(p1, input_digest="in1"), [i1], [_citation(p1, i1["packet_item_id"])],
                       _receipt(p1, "in1"))
    res = repo.upsert_packet(_header(p2, input_digest="in2"), [i2], [_citation(p2, i2["packet_item_id"])],
                             _receipt(p2, "in2"))
    assert res["created"] is True and res["superseded"] == [p1]
    assert repo.get_research_packet(p1)["status"] == "superseded"
    assert repo.get_research_packet(p2)["status"] == "built"


def test_independent_projection_lineage_coexists(repo: ResearchPacketRepository) -> None:
    ia, ib = _item("x"), _item("y")
    repo.upsert_packet(_header("x", projection="projA"), [ia], [_citation("x", ia["packet_item_id"])],
                       _receipt("x"))
    repo.upsert_packet(_header("y", projection="projB"), [ib], [_citation("y", ib["packet_item_id"])],
                       _receipt("y"))
    assert repo.count() == 2  # different projection lineages never supersede each other


def test_mark_stale_if_needed(repo: ResearchPacketRepository) -> None:
    pid = "pkS"
    i = _item(pid)
    repo.upsert_packet(_header(pid, input_digest="in1"), [i], [_citation(pid, i["packet_item_id"])],
                       _receipt(pid, "in1"))
    res = repo.mark_research_packet_stale_if_needed(pid, current_input_digest="in-DIFFERENT")
    assert res["stale"] is True
    assert repo.get_research_packet(pid)["status"] == "stale"


def test_summary_shape(repo: ResearchPacketRepository) -> None:
    i = _item("s1")
    repo.upsert_packet(_header("s1"), [i], [_citation("s1", i["packet_item_id"])], _receipt("s1"))
    s = repo.summary()
    assert s["total_packets"] == 1 and s["total_items"] == 1 and s["total_citations"] == 1
    assert "by_packet_type" in s and "by_status" in s
