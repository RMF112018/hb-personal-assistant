"""Phase 08A evaluation preview + Output Evaluation Agent (A05) proof (Prompts 08, 12).

A deterministic pre-presentation checklist over the repo ``evaluation_criteria_contract``
checklist items, computed from the synthesized `AdapterResult` + research packet + bounded
`ContextEnvelope`. Prompt 12 adds the Output Evaluation Agent (A05) persistence (see
``store.py::write_evaluation_run``) which records this checklist into the V26
``second_brain_evaluation_runs`` table; ``build_output_evaluation_agent_proof`` exercises
the pass + fail paths. No raw content.
"""

from __future__ import annotations

from typing import Any

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
        "advisory_vs_actionable_classified": adapter_result.disposition
        in (
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


def _evaluate_db(
    db_path: str, *, question: str
) -> tuple[EvaluationPreview, AdapterResult, ResearchPacket]:
    """Retrieve -> packet -> mock synthesize -> evaluate over one local DB (helper)."""
    from ..reasoning import MockClaudeAdapter
    from ..research import build_research_packet_from_envelope
    from ..retrieval import ALLOWLISTED_SOURCE_FAMILIES, RetrievalBroker

    envelope = RetrievalBroker(db_path=db_path).retrieve(
        project_key="P1", families=ALLOWLISTED_SOURCE_FAMILIES, emit_receipt=False
    )
    packet, assessment, _rid, _pid = build_research_packet_from_envelope(
        envelope,
        packet_type="daily_brief",
        requested=ALLOWLISTED_SOURCE_FAMILIES,
        project_key="P1",
        db_path=db_path,
        emit_receipt=False,
    )
    ctx = envelope.to_context_envelope(
        question=question, research_packet_ok=packet.degradation_mode != "blocked"
    )
    result = MockClaudeAdapter().synthesize(ctx)
    evaluation = build_evaluation_preview(
        adapter_result=result, packet=packet, assessment=assessment, envelope=ctx
    )
    return evaluation, result, packet


def build_output_evaluation_agent_proof() -> dict[str, Any]:
    """Deterministic proof for ``output-evaluation-agent-proof.json`` (temp DBs)."""
    import json
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    from .store import write_evaluation_run

    with tempfile.TemporaryDirectory() as tmp:
        seeded = f"{tmp}/seeded.sqlite3"
        store = ConstructionStore(seeded)
        store.upsert_cross_source_relationship(
            relationship_id="rel-1",
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
        passed_eval, passed_result, passed_packet = _evaluate_db(
            seeded, question="daily brief 2026-06-02"
        )
        passed_id = write_evaluation_run(
            evaluation=passed_eval,
            target_kind="daily_brief",
            target_id=passed_packet.packet_id,
            research_packet_id=passed_packet.packet_id,
            confidence_class=passed_result.confidence,
            review_tier_reason_code=passed_result.review_reason_code,
            degradation_mode=passed_result.degradation_mode,
            mode="dry_run",
            db_path=seeded,
        )

        empty = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty)
        failed_eval, failed_result, failed_packet = _evaluate_db(
            empty, question="daily brief 2026-06-02"
        )
        failed_id = write_evaluation_run(
            evaluation=failed_eval,
            target_kind="daily_brief",
            target_id=failed_packet.packet_id,
            research_packet_id=failed_packet.packet_id,
            confidence_class=failed_result.confidence,
            review_tier_reason_code=failed_result.review_reason_code,
            degradation_mode=failed_result.degradation_mode,
            mode="dry_run",
            db_path=empty,
        )

        c = sqlite3.connect(seeded)
        c.row_factory = sqlite3.Row
        passed_row = dict(c.execute("SELECT * FROM second_brain_evaluation_runs").fetchone())
        c.close()

    guards_zero = all(
        passed_row[col] == 0
        for col in passed_row
        if col.endswith("_persisted") or col == "external_writeback_performed"
    )
    blob = json.dumps(passed_eval.model_dump()) + json.dumps(failed_eval.model_dump())
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        passed_id
        and failed_id
        and passed_eval.passed is True
        and failed_eval.passed is False
        and failed_eval.checklist["source_references_present"] is False
        and passed_row["passed"] == 1
        and passed_row["review_status"] == "pending_review"
        and passed_row["checklist_total"] == 10
        and guards_zero
        and no_raw_content
    )
    return {
        "proof": "phase_08a_output_evaluation_agent",
        "proof_passed": proof_passed,
        "passed_case": {
            "evaluation_run_id": passed_id,
            "passed": passed_eval.passed,
            "score": passed_eval.score,
            "checklist_passed": passed_eval.checklist_passed,
            "checklist_total": passed_eval.checklist_total,
            "review_tier": passed_eval.review_tier,
        },
        "failed_case": {
            "evaluation_run_id": failed_id,
            "passed": failed_eval.passed,
            "score": failed_eval.score,
            "source_references_present": failed_eval.checklist["source_references_present"],
        },
        "evaluation_run_persisted": bool(passed_id and failed_id),
        "guard_columns_zero": guards_zero,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "block_on_policy_failure": True,
            "evaluation_in_dry_run_where_output_generated": True,
            "model_direct_external_api_access": False,
        },
    }
