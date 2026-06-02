"""Phase 08A evaluation preview (Prompt 08).

A deterministic pre-presentation checklist over the repo
``evaluation_criteria_contract`` checklist items, computed from the synthesized
`AdapterResult` + research packet + bounded `ContextEnvelope`. This is a *preview* — it
is not persisted; the full Output Evaluation Agent (A05) + ``second_brain_evaluation_runs``
writes are deferred to a later prompt. No raw content.
"""

from __future__ import annotations

from ..reasoning import AdapterResult, ContextEnvelope
from ..research import ResearchPacket, ResearchPacketAssessment
from .models import EvaluationPreview

_FORBIDDEN_TOKENS = (
    "raw_url",
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
    "token",
)


def build_evaluation_preview(
    *,
    adapter_result: AdapterResult,
    packet: ResearchPacket,
    assessment: ResearchPacketAssessment,
    envelope: ContextEnvelope,
) -> EvaluationPreview:
    """Compute the deterministic evaluation checklist preview."""
    blob = adapter_result.model_dump_json()
    insufficient = (
        envelope.context_quality == "insufficient" or packet.degradation_mode == "blocked"
    )

    checklist: dict[str, bool] = {
        "source_references_present": len(adapter_result.source_references) > 0,
        "review_tiers_assigned": adapter_result.review_tier in (1, 2, 3),
        "confidence_class_present": bool(adapter_result.confidence),
        "stale_unknown_warnings_surfaced": (
            assessment.stale_unknown_count == 0
            or bool(adapter_result.stale_unknown_warnings or envelope.stale_unknown_warnings)
        ),
        "conflict_warnings_surfaced": (
            assessment.conflict_count == 0
            or bool(adapter_result.conflict_warnings or envelope.conflict_warnings)
        ),
        "coverage_warnings_surfaced": (
            not (assessment.families_missing or assessment.policy_warnings)
            or bool(adapter_result.coverage_warnings or envelope.coverage_warnings)
        ),
        "advisory_vs_actionable_classified": adapter_result.disposition in (
            "advisory",
            "actionable",
        ),
        # A Tier-3 result must never be synthesized as an accepted fact.
        "no_tier_3_treated_as_accepted_fact": not (
            adapter_result.review_tier == 3 and adapter_result.synthesized
        ),
        "no_raw_content_in_output": not any(t in blob for t in _FORBIDDEN_TOKENS),
        "degradation_mode_set_when_insufficient": (
            adapter_result.degradation_mode != "none" if insufficient else True
        ),
    }

    total = len(checklist)
    passed_count = sum(1 for v in checklist.values() if v)
    return EvaluationPreview(
        checklist=checklist,
        checklist_total=total,
        checklist_passed=passed_count,
        score=round(passed_count / total, 4) if total else 0.0,
        passed=all(checklist.values()),
        review_tier=adapter_result.review_tier,
        review_status=adapter_result.review_status,
    )
