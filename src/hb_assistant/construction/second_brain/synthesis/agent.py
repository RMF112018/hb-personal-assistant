"""Phase 08A Answer Synthesis Agent (A04) — Synthesized Prompt 08.

Source-linked, research-first interactive Q&A. Retrieves bounded context once, builds a
research packet (the complex-query discipline), maps the context into a `ContextEnvelope`,
and runs it through the Claude adapter's pre-synthesis gate (mock-first, offline). The
result separates advisory intelligence from actionable recommendations, labels claim
strength, and preserves Tier-3 mandatory-review treatment — high-impact / Tier-3 items are
visible but never presented as final conclusions. No model auto-selects live; no raw
content; answers are not persisted.
"""

from __future__ import annotations

from typing import Any

from ..config import SecondBrainConfig, load_second_brain_config
from ..reasoning import ClaudeAdapter, MockClaudeAdapter, build_claude_adapter
from ..research import build_research_packet_from_envelope
from ..retrieval import ALLOWLISTED_SOURCE_FAMILIES, RetrievalBroker
from .evaluation import build_evaluation_preview
from .models import QueryResult

_ADVISORY_NOTE = (
    "Advisory intelligence only. High-impact / Tier-3 items are routed to mandatory "
    "review and are never presented as final conclusions."
)


def _claim_strength(*, synthesized: bool, degradation_mode: str) -> str:
    if not synthesized:
        return "insufficient"
    return "strong" if degradation_mode == "none" else "qualified"


def synthesize_answer(
    *,
    question: str,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    db_path: str | None = None,
    config: SecondBrainConfig | None = None,
    adapter: ClaudeAdapter | None = None,
    emit_receipt: bool = False,
) -> QueryResult:
    """Run a source-linked, research-first interactive query; returns a `QueryResult`."""
    requested = families or ALLOWLISTED_SOURCE_FAMILIES
    envelope = RetrievalBroker(db_path=db_path).retrieve(
        project_key=project_key, families=requested, emit_receipt=False
    )
    packet, assessment, retrieval_receipt_id, packet_receipt_id = (
        build_research_packet_from_envelope(
            envelope,
            packet_type="interactive_query",
            requested=tuple(requested),
            project_key=project_key,
            db_path=db_path,
            emit_receipt=emit_receipt,
        )
    )
    research_packet_ok = packet.degradation_mode != "blocked"
    context = envelope.to_context_envelope(
        question=question, research_packet_ok=research_packet_ok
    )

    # Mock-first: never auto-select live (only an explicitly-live config yields it).
    resolved_adapter = (
        adapter or build_claude_adapter(config or load_second_brain_config()) or MockClaudeAdapter()
    )
    result = resolved_adapter.synthesize(context)
    evaluation = build_evaluation_preview(
        adapter_result=result, packet=packet, assessment=assessment, envelope=context
    )

    claim_strength = _claim_strength(
        synthesized=result.synthesized, degradation_mode=result.degradation_mode
    )
    warnings = sorted(
        set(result.coverage_warnings)
        | set(result.stale_unknown_warnings)
        | set(result.conflict_warnings)
        | set(assessment.policy_warnings)
    )
    if not result.synthesized:
        warnings.append("synthesis_blocked:context_or_tier_gate")
    if result.degradation_mode != "none":
        warnings.append(f"degradation_mode:{result.degradation_mode}")

    confidence_labels: dict[str, Any] = {
        "overall": result.confidence,
        "claim_strength": claim_strength,
        "review_tier": result.review_tier,
        "review_reason_code": result.review_reason_code,
    }
    review_tiers: dict[str, Any] = {
        "max_tier": result.review_tier,
        "review_status": result.review_status,
        "distribution": assessment.review_tier_distribution,
    }
    research_packet_summary: dict[str, Any] = {
        "packet_id": packet.packet_id,
        "context_quality_class": packet.context_quality_class,
        "degradation_mode": packet.degradation_mode,
        "source_ref_count": packet.source_ref_count,
        "source_coverage": assessment.source_coverage,
        "open_questions_count": len(assessment.open_questions),
    }
    advisory_vs_actionable_marking: dict[str, Any] = {
        "disposition": result.disposition,
        "actionable_recommendations": [],
        "advisory_note": _ADVISORY_NOTE,
    }

    return QueryResult(
        answer_redacted=result.answer,
        source_refs=result.source_references,
        confidence_labels=confidence_labels,
        review_tiers=review_tiers,
        research_packet_summary=research_packet_summary,
        evaluation_summary=evaluation.model_dump(),
        warnings=sorted(set(warnings)),
        advisory_vs_actionable_marking=advisory_vs_actionable_marking,
        synthesized=result.synthesized,
        mode=result.mode,
        retrieval_receipt_id=retrieval_receipt_id,
        packet_receipt_id=packet_receipt_id,
    )


def build_answer_synthesis_agent_proof() -> dict[str, Any]:
    """Deterministic proof for ``answer-synthesis-agent-proof.md`` (temp DBs, mock)."""
    import json
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    def _seed_tier1(db_path: str) -> None:
        store = ConstructionStore(db_path)
        store.upsert_cross_source_relationship(
            relationship_id="rel-accepted",
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
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO long_term_memory_items "
            "(memory_id, memory_type, statement_redacted, project_key, confidence_class, "
            " review_status) VALUES ('mem1','fact','kickoff confirmed','P1','high','accepted')"
        )
        conn.commit()
        conn.close()

    def _seed_tier3(db_path: str) -> None:
        store = ConstructionStore(db_path)
        store.upsert_cross_source_relationship(
            relationship_id="rel-review",
            source_family="email",
            source_record_type="message",
            source_record_ref="m9",
            target_family="financial",
            target_record_type="invoice",
            target_record_ref="inv9",
            relationship_type="references",
            confidence_class="weak_heuristic",
            source_reference_json=json.dumps({"project_key": "P1"}),
            project_key="P1",
            promotion_status="promoted",
            promoted_by="human",
            review_required=True,
        )

    with tempfile.TemporaryDirectory() as tmp:
        db_a = f"{tmp}/tier1.sqlite3"
        db_b = f"{tmp}/tier3.sqlite3"
        _seed_tier1(db_a)
        _seed_tier3(db_b)

        synthesized = synthesize_answer(
            question="What changed on the pilot project this week?",
            project_key="P1",
            db_path=db_a,
            adapter=MockClaudeAdapter(),
            emit_receipt=False,
        )
        blocked = synthesize_answer(
            question="Is the contractor entitled to this claim?",
            project_key="P1",
            db_path=db_b,
            adapter=MockClaudeAdapter(),
            emit_receipt=False,
        )

    blob = synthesized.model_dump_json() + blocked.model_dump_json()
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body", "raw_document_text", "raw_calendar_payload", "raw_prompt",
            "raw_response", "signed_url", "download_url", "secret",
        )
    )
    required_output = {
        "answer_redacted", "source_refs", "confidence_labels", "review_tiers",
        "research_packet_summary", "evaluation_summary", "warnings",
        "advisory_vs_actionable_marking",
    }
    has_required = required_output <= set(synthesized.model_dump())

    synth_ok = (
        synthesized.synthesized is True
        and synthesized.mode == "mock"
        and len(synthesized.source_refs) >= 1
        and synthesized.advisory_vs_actionable_marking["disposition"] == "advisory"
        and synthesized.evaluation_summary["passed"] is True
    )
    blocked_ok = (
        blocked.synthesized is False
        and blocked.review_tiers["review_status"] == "review_required"
        and blocked.answer_redacted == ""
        and any(w.startswith("synthesis_blocked") for w in blocked.warnings)
        and blocked.evaluation_summary["checklist"]["no_tier_3_treated_as_accepted_fact"] is True
    )

    proof_passed = bool(synth_ok and blocked_ok and has_required and no_raw_content)
    return {
        "proof": "phase_08a_answer_synthesis_agent",
        "proof_passed": proof_passed,
        "synthesized_query": {
            "synthesized": synthesized.synthesized,
            "mode": synthesized.mode,
            "source_ref_count": len(synthesized.source_refs),
            "claim_strength": synthesized.confidence_labels.get("claim_strength"),
            "review_tier": synthesized.review_tiers.get("max_tier"),
            "evaluation_passed": synthesized.evaluation_summary["passed"],
            "evaluation_score": synthesized.evaluation_summary["score"],
            "answer_redacted": synthesized.answer_redacted,
        },
        "high_impact_query": {
            "synthesized": blocked.synthesized,
            "review_status": blocked.review_tiers.get("review_status"),
            "degradation_mode": blocked.research_packet_summary.get("degradation_mode"),
            "no_tier_3_treated_as_accepted_fact": blocked.evaluation_summary["checklist"][
                "no_tier_3_treated_as_accepted_fact"
            ],
            "warnings": blocked.warnings,
        },
        "required_output_fields_present": has_required,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "mock_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "research_packet_required_for_complex": True,
            "tier_3_never_final_conclusion": True,
            "model_direct_external_api_access": False,
        },
    }
