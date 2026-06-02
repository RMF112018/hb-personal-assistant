"""Phase 08A Prompt 08 — deterministic evaluation preview checklist."""

from __future__ import annotations

from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.reasoning import AdapterResult, ContextEnvelope
from hb_assistant.construction.second_brain.research import ResearchPacket, ResearchPacketAssessment
from hb_assistant.construction.second_brain.synthesis import build_evaluation_preview


def _packet(degradation_mode: str = "graceful_degraded") -> ResearchPacket:
    return ResearchPacket(
        packet_id="p1",
        topic_hash="h1",
        degradation_mode=degradation_mode,  # type: ignore[arg-type]
        context_quality_class="partial",
    )


def _assessment() -> ResearchPacketAssessment:
    return ResearchPacketAssessment()


def _envelope(*, tier: int, quality: str) -> ContextEnvelope:
    return ContextEnvelope(
        question="q",
        source_references=[{"source_family": "x", "source_ref": "r1"}],
        review_tier=tier,
        confidence_class="medium" if tier != 3 else "low",
        research_packet_ok=True,
        context_quality=quality,  # type: ignore[arg-type]
    )


def _synth_result(*, tier: int, synthesized: bool, degradation: str) -> AdapterResult:
    return AdapterResult(
        answer="[mock advisory synthesis] advisory only." if synthesized else "",
        mode="mock",
        synthesized=synthesized,
        source_references=[{"source_family": "x", "source_ref": "r1"}],
        confidence="medium" if tier != 3 else "low",
        review_tier=tier,
        review_reason_code="T1_DETERMINISTIC_SOURCE_BACKED" if tier == 1 else "T3_MODEL_ONLY",
        review_status="auto_advisory" if tier == 1 else "review_required",
        disposition="advisory",
        degradation_mode=degradation,  # type: ignore[arg-type]
    )


def test_preview_covers_the_contract_checklist_items() -> None:
    contract = load_phase_08a_contract("evaluation_criteria_contract")
    preview = build_evaluation_preview(
        adapter_result=_synth_result(tier=1, synthesized=True, degradation="none"),
        packet=_packet("none"),
        assessment=_assessment(),
        envelope=_envelope(tier=1, quality="sufficient"),
    )
    assert set(preview.checklist) == set(contract["checklist_items"])
    assert preview.checklist_total == 10


def test_clean_tier1_passes() -> None:
    preview = build_evaluation_preview(
        adapter_result=_synth_result(tier=1, synthesized=True, degradation="none"),
        packet=_packet("none"),
        assessment=_assessment(),
        envelope=_envelope(tier=1, quality="sufficient"),
    )
    assert preview.passed is True
    assert preview.score == 1.0
    assert preview.checklist_passed == 10


def test_tier3_synthesized_fails_no_accepted_fact_check() -> None:
    # A (hypothetical) Tier-3 result presented as synthesized fact must fail the check.
    preview = build_evaluation_preview(
        adapter_result=_synth_result(tier=3, synthesized=True, degradation="graceful_degraded"),
        packet=_packet("graceful_degraded"),
        assessment=_assessment(),
        envelope=_envelope(tier=3, quality="partial"),
    )
    assert preview.checklist["no_tier_3_treated_as_accepted_fact"] is False
    assert preview.passed is False


def test_blocked_sets_degradation_mode_when_insufficient() -> None:
    preview = build_evaluation_preview(
        adapter_result=_synth_result(tier=3, synthesized=False, degradation="blocked"),
        packet=_packet("blocked"),
        assessment=_assessment(),
        envelope=_envelope(tier=3, quality="insufficient"),
    )
    assert preview.checklist["degradation_mode_set_when_insufficient"] is True
    assert preview.checklist["no_tier_3_treated_as_accepted_fact"] is True
