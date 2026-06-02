"""Phase 08A Prompt 11 — Review Triage Agent (review_triage_agent)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.daily_brief import (
    ReviewTriageAgent,
    build_review_load_status,
    build_review_triage_agent_proof,
)
from hb_assistant.construction.second_brain.retrieval import RetrievalItem
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "triage.sqlite")


def _seed(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_cross_source_relationship(
        relationship_id="rel-ok",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )
    store.upsert_cross_source_relationship(
        relationship_id="rel-review",
        source_family="email",
        source_record_type="message",
        source_record_ref="m2",
        target_family="financial",
        target_record_type="invoice",
        target_record_ref="inv1",
        relationship_type="references",
        confidence_class="model_proposed",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=True,
    )


def test_review_load_grouped_by_tier_source_project_urgency() -> None:
    items = [
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="iss-1",
            record_type="issue",
            record_ref="iss-1",
            project_key="P1",
            confidence_class="medium",
            review_tier=2,
            review_status="review_recommended",
            review_required=False,
            stale_unknown_flags=["stale_status"],
        ),
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="rel-review",
            record_type="relationship",
            record_ref="rel-review",
            project_key="P2",
            confidence_class="low",
            review_tier=3,
            review_status="review_required",
            review_required=True,
        ),
    ]
    status = build_review_load_status(items)
    assert status.total_review_items == 2
    assert status.by_tier == {"1": 0, "2": 1, "3": 1}
    assert status.by_source_family["cross_source_relationships"] == 1
    assert status.by_project == {"P1": 1, "P2": 1}
    assert status.by_urgency["high"] == 1  # the tier-3 review_required item
    assert status.by_urgency["medium"] == 1  # the tier-2 / stale item
    assert status.tier_3_count == 1
    assert status.mandatory_review_count == 1


def test_auto_advisory_items_are_not_review_load() -> None:
    items = [
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="rel-ok",
            record_type="relationship",
            record_ref="rel-ok",
            project_key="P1",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
        )
    ]
    status = build_review_load_status(items)
    assert status.total_review_items == 0
    assert status.tier_3_count == 0


def test_agent_summarize_over_seeded_db(db_path: str) -> None:
    _seed(db_path)
    status = ReviewTriageAgent(db_path=db_path).summarize(project_key="P1")
    assert status.tier_3_count >= 1
    assert status.mandatory_review_count >= 1
    assert status.by_project.get("P1", 0) >= 1


def test_empty_db_has_no_review_load(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only
    status = ReviewTriageAgent(db_path=db_path).summarize(project_key="P1")
    assert status.total_review_items == 0
    assert status.tier_3_count == 0


def test_review_triage_agent_proof_passes() -> None:
    proof = build_review_triage_agent_proof()
    assert proof["proof_passed"] is True
    assert proof["grouped_by_tier_source_project_urgency"] is True
    assert proof["tier_3_surfaced_as_mandatory_review"] is True
    assert proof["no_raw_content"] is True
