"""Phase 08A Synthesized Prompt 04 — retrieval policy + context budget (offline)."""

from __future__ import annotations

import json

from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.retrieval import (
    ALLOWLISTED_SOURCE_FAMILIES,
    EXCLUDED_FAMILIES,
    apply_context_budget,
    build_retrieval_broker_agent_proof,
    derive_relationship_state,
    load_context_budget,
    relationship_state_tier,
    validate_retrieval_policy,
)
from hb_assistant.construction.second_brain.retrieval.models import RetrievalItem


def test_policy_validates() -> None:
    report = validate_retrieval_policy()
    assert report["valid"] is True
    assert report["violations"] == []
    assert report["approved_count"] == 8


def test_allowlist_disjoint_from_excluded() -> None:
    assert not (set(ALLOWLISTED_SOURCE_FAMILIES) & EXCLUDED_FAMILIES)


def test_budget_satisfies_contract() -> None:
    budget = load_context_budget()
    contract = load_phase_08a_contract("context_budget_contract")
    for field in contract["required_fields"]:
        assert hasattr(budget, field), f"budget missing {field}"
    assert budget.max_context_chars == 24000
    assert budget.deterministic_truncation is True


def test_relationship_state_precedence() -> None:
    assert derive_relationship_state({"promotion_status": "rejected"}) == "rejected_excluded"
    assert derive_relationship_state({"promotion_status": "promoted"}) == "accepted_human_promoted"
    assert derive_relationship_state({"deterministic": True}) == "authoritative_deterministic"
    assert derive_relationship_state({"sensitive_high_impact": True}) == "sensitive_review_required"
    assert derive_relationship_state({"model_proposed": True}) == "model_proposed_review_required"
    assert derive_relationship_state({"confidence_class": "high"}) == "suggested_strong"
    assert derive_relationship_state({}) == "suggested_weak"
    assert relationship_state_tier("sensitive_review_required") == 3
    assert relationship_state_tier("authoritative_deterministic") == 1


def test_budget_truncates_deterministically() -> None:
    budget = load_context_budget()
    items = [
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref=f"r{i}",
            record_type="relationship",
            record_ref=f"r{i}",
            review_tier=1 if i == 0 else 3,
            review_status="auto_advisory" if i == 0 else "review_required",
            review_required=i != 0,
            content_excerpt_redacted="x" * 1000,
            recency=f"2026-05-{10 + i:02d}",
        )
        for i in range(40)
    ]
    kept, char_count, truncated, degradation = apply_context_budget(items, budget)
    assert truncated is True
    assert char_count <= budget.max_context_chars
    assert degradation == "narrow_claims"
    # Tier 1 retained first (deterministic priority).
    assert kept[0].review_tier == 1
    # Stable/deterministic: repeat run yields identical ordering.
    kept2, _, _, _ = apply_context_budget(items, budget)
    assert [i.source_ref for i in kept] == [i.source_ref for i in kept2]


def test_per_item_excerpt_capped() -> None:
    budget = load_context_budget()
    items = [
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="big",
            record_type="relationship",
            record_ref="big",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
            content_excerpt_redacted="y" * 5000,
        )
    ]
    kept, _, _, _ = apply_context_budget(items, budget)
    assert len(kept[0].content_excerpt_redacted) == budget.max_item_chars


def test_item_rejects_forbidden_raw_field_name() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RetrievalItem(
            source_family="signed_url",  # forbidden raw field name
            source_ref="x",
            record_type="t",
            record_ref="r",
        )


def test_broker_agent_proof_passes() -> None:
    proof = build_retrieval_broker_agent_proof()
    assert proof["proof"] == "phase_08a_retrieval_broker_agent"
    assert proof["proof_passed"] is True
    assert proof["tier3_visible_not_concluded"] is True
    assert proof["no_raw_content"] is True
    assert proof["no_raw_source_access"] is True
    assert proof["no_arbitrary_sql"] is True
    assert proof["budget_enforced"] is True
    assert proof["guardrails"]["mcp_implemented"] is False
    assert "signed_url" in proof["denied_families"]
    # No raw *content* leaked (denied_families lists policy labels only).
    assert "raw_body" not in json.dumps(proof)
