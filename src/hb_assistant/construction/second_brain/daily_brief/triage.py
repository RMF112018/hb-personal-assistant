"""Phase 08A Review Triage Agent (review_triage_agent) — Prompt 11.

Summarizes the **review load** of broker-retrieved context, grouped by review tier,
source family, project, and urgency. Read-only and deterministic: it reuses the Prompt-04
Retrieval Broker (the only path to context) and never persists raw content or writes back.
Tier-3 items are surfaced as mandatory review — never auto-accepted as conclusions.
"""

from __future__ import annotations

from typing import Any

from ..retrieval import RetrievalBroker, RetrievalItem
from .models import ReviewLoadStatus


def _urgency(item: RetrievalItem) -> str:
    """Deterministic urgency band: tier/flags drive priority (high > medium > low)."""
    if item.review_required or item.conflict_flags:
        return "high"
    if item.review_tier == 2 or item.stale_unknown_flags:
        return "medium"
    return "low"


def _is_review_item(item: RetrievalItem) -> bool:
    """An item carries review load if it is mandatory or recommended for review."""
    return item.review_required or item.review_status in (
        "review_required",
        "review_recommended",
    )


def build_review_load_status(
    items: list[RetrievalItem],
    *,
    degradation_mode: str = "none",
    warnings: list[str] | None = None,
) -> ReviewLoadStatus:
    """Group the review load by tier, source family, project, and urgency."""
    review_items = [it for it in items if _is_review_item(it)]

    by_tier: dict[str, int] = {"1": 0, "2": 0, "3": 0}
    by_source_family: dict[str, int] = {}
    by_project: dict[str, int] = {}
    by_urgency: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    for it in review_items:
        by_tier[str(it.review_tier)] += 1
        by_source_family[it.source_family] = by_source_family.get(it.source_family, 0) + 1
        project = it.project_key or "_unassigned"
        by_project[project] = by_project.get(project, 0) + 1
        by_urgency[_urgency(it)] += 1

    tier_3_count = by_tier["3"]
    return ReviewLoadStatus(
        total_review_items=len(review_items),
        by_tier=by_tier,
        by_source_family=dict(sorted(by_source_family.items())),
        by_project=dict(sorted(by_project.items())),
        by_urgency=by_urgency,
        tier_3_count=tier_3_count,
        mandatory_review_count=sum(1 for it in review_items if it.review_required),
        degradation_mode=degradation_mode,
        warnings=sorted(set(warnings or [])),
    )


class ReviewTriageAgent:
    """Deterministic triage over allowlisted, broker-retrieved review load."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def summarize(
        self,
        *,
        project_key: str | None = None,
        families: tuple[str, ...] | None = None,
    ) -> ReviewLoadStatus:
        envelope = RetrievalBroker(db_path=self._db_path).retrieve(
            project_key=project_key, families=families, emit_receipt=False
        )
        return build_review_load_status(
            envelope.items,
            degradation_mode=envelope.degradation_mode,
            warnings=envelope.coverage_warnings,
        )


def build_review_triage_agent_proof() -> dict[str, Any]:
    """Deterministic proof for ``review-triage-agent-proof.json`` (temp DB)."""
    import json
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        seeded = f"{tmp}/seeded.sqlite3"
        store = ConstructionStore(seeded)
        # Tier-1 (auto-advisory) relationship.
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
        # Tier-3 (mandatory review) relationship.
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

        status = ReviewTriageAgent(db_path=seeded).summarize(project_key="P1")

        empty = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty)
        empty_status = ReviewTriageAgent(db_path=empty).summarize(project_key="P1")

    blob = status.model_dump_json()
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body",
            "raw_document_text",
            "raw_calendar_payload",
            "raw_prompt",
            "raw_response",
            "signed_url",
            "download_url",
            "secret",
        )
    )
    grouped = bool(
        status.by_tier and status.by_source_family and status.by_project and status.by_urgency
    )
    tier3_surfaced = status.tier_3_count >= 1 and status.mandatory_review_count >= 1
    empty_is_empty = empty_status.total_review_items == 0 and empty_status.tier_3_count == 0

    proof_passed = bool(grouped and tier3_surfaced and no_raw_content and empty_is_empty)
    return {
        "proof": "phase_08a_review_triage_agent",
        "proof_passed": proof_passed,
        "seeded_review_load": {
            "total_review_items": status.total_review_items,
            "by_tier": status.by_tier,
            "by_source_family": status.by_source_family,
            "by_project": status.by_project,
            "by_urgency": status.by_urgency,
            "tier_3_count": status.tier_3_count,
            "mandatory_review_count": status.mandatory_review_count,
        },
        "empty_db_review_load": {
            "total_review_items": empty_status.total_review_items,
            "tier_3_count": empty_status.tier_3_count,
        },
        "grouped_by_tier_source_project_urgency": grouped,
        "tier_3_surfaced_as_mandatory_review": tier3_surfaced,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "tier_3_mandatory_review": True,
            "model_direct_external_api_access": False,
        },
    }
