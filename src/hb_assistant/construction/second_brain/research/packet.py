"""Phase 08A Research Packet Agent (A02) — Synthesized Prompt 07.

Assembles a bounded, redacted pre-synthesis research packet: source coverage,
stale/unknown + conflict counts, review-tier density, accepted-memory refs, open
questions, policy warnings, and a graceful-degradation recommendation. Reuses the
Prompt-04 Retrieval Broker (the only path to context) + its receipt writer; persists a
metadata-only packet receipt. No model, no raw content, no external access.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..retrieval import (
    ALLOWLISTED_SOURCE_FAMILIES,
    RetrievalBroker,
    RetrievalEnvelope,
    write_retrieval_receipt,
)
from ..retrieval.readers import READER_REGISTRY
from .models import ResearchPacket, ResearchPacketAssessment
from .policy import score_context_quality
from .store import write_research_packet_receipt

_OPEN_QUESTION_TIER3_LIMIT = 5


def _topic_hash(packet_type: str, project_key: str | None, requested: tuple[str, ...]) -> str:
    payload = f"{packet_type}|{project_key or ''}|{','.join(sorted(requested))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _assess(
    envelope: RetrievalEnvelope, requested: tuple[str, ...]
) -> tuple[ResearchPacketAssessment, dict[str, Any]]:
    items = envelope.items
    total = len(items)
    backed_requested = [f for f in requested if f in READER_REGISTRY]
    families_present = sorted({it.source_family for it in items})
    families_missing = [f for f in backed_requested if f not in families_present]
    source_coverage = (len(families_present) / len(backed_requested)) if backed_requested else 0.0
    complete = sum(1 for it in items if it.source_family and it.source_ref)
    source_ref_completeness = (complete / total) if total else 0.0

    tier3 = [it for it in items if it.review_tier == 3]
    accepted_memory_refs = [
        {"source_family": it.source_family, "source_ref": it.source_ref}
        for it in items
        if it.source_family == "accepted_long_term_memory"
    ]

    open_questions: list[str] = [f"coverage_gap:no_{fam}_retrieved" for fam in families_missing]
    open_questions += [
        f"tier_3_review_required:{it.source_family}:{it.source_ref}"
        for it in tier3[:_OPEN_QUESTION_TIER3_LIMIT]
    ]
    open_questions += [f"conflict:{w}" for w in envelope.conflict_warnings]
    if envelope.truncated:
        open_questions.append("context_truncated_by_budget")

    score = score_context_quality(
        total_items=total,
        tier3_count=envelope.tier_distribution.get("3", 0),
        stale_unknown_count=len(envelope.stale_unknown_warnings),
        conflict_count=len(envelope.conflict_warnings),
        source_ref_completeness=source_ref_completeness,
        source_coverage=source_coverage,
    )
    policy_warnings = sorted(set(envelope.coverage_warnings) | set(score["policy_warnings"]))

    assessment = ResearchPacketAssessment(
        families_present=families_present,
        families_missing=families_missing,
        source_coverage=round(source_coverage, 4),
        source_ref_completeness=round(source_ref_completeness, 4),
        review_tier_distribution=dict(envelope.tier_distribution),
        stale_unknown_count=len(envelope.stale_unknown_warnings),
        conflict_count=len(envelope.conflict_warnings),
        accepted_memory_refs=accepted_memory_refs,
        open_questions=open_questions,
        policy_warnings=policy_warnings,
        degradation_recommendation=score["degradation_recommendation"],
    )
    return assessment, score


def build_research_packet(
    *,
    packet_type: str,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    db_path: str | None = None,
    emit_receipt: bool = True,
) -> tuple[ResearchPacket, ResearchPacketAssessment, str | None, str | None]:
    """Build a research packet from broker-retrieved context.

    Returns (packet, assessment, retrieval_receipt_id|None, packet_receipt_id|None).
    """
    requested = families or ALLOWLISTED_SOURCE_FAMILIES
    envelope = RetrievalBroker(db_path=db_path).retrieve(
        project_key=project_key, families=requested, emit_receipt=False
    )
    # Own the retrieval receipt so we can link it to the packet (gated by emit_receipt
    # so --no-emit-receipt is fully dry — no local DB writes).
    retrieval_receipt_id: str | None = None
    if emit_receipt:
        retrieval_receipt_id = write_retrieval_receipt(
            envelope, requested=tuple(requested), db_path=db_path
        )

    assessment, score = _assess(envelope, tuple(requested))
    items = envelope.items
    review_tier = max((it.review_tier for it in items), default=3)
    reason = "T3_MANDATORY_REVIEW" if review_tier == 3 else "T1_SOURCE_BACKED"
    status = "blocked" if score["degradation_mode"] == "blocked" else "assembled"
    summary = (
        f"{packet_type} coverage={len(assessment.families_present)}/"
        f"{len(assessment.families_present) + len(assessment.families_missing)} "
        f"items={len(items)} tier3={envelope.tier_distribution.get('3', 0)} "
        f"stale={assessment.stale_unknown_count} conflicts={assessment.conflict_count} "
        f"{score['degradation_mode']}"
    )

    packet = ResearchPacket(
        packet_id=_topic_hash(packet_type, project_key, tuple(requested))[:32],
        topic_hash=_topic_hash(packet_type, project_key, tuple(requested)),
        project_key=project_key,
        retrieval_receipt_id=retrieval_receipt_id,
        source_ref_count=len(items),
        review_required_count=sum(1 for it in items if it.review_required),
        stale_unknown_count=assessment.stale_unknown_count,
        conflict_count=assessment.conflict_count,
        context_quality_class=score["context_quality_class"],
        degradation_mode=score["degradation_mode"],
        confidence_class=score["confidence_class"],
        review_tier=review_tier,
        review_tier_reason_code=reason,
        review_status="pending_review",
        advisory_classification="advisory",
        coverage_warnings=assessment.policy_warnings,
        summary_redacted=summary,
        status=status,
    )

    packet_receipt_id: str | None = None
    if emit_receipt:
        packet_receipt_id = write_research_packet_receipt(packet=packet, db_path=db_path)
    return packet, assessment, retrieval_receipt_id, packet_receipt_id


def build_research_packet_agent_proof() -> dict[str, Any]:
    """Deterministic proof for ``research-packet-agent-proof.json`` (temp DB)."""
    import json
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

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
        conn = sqlite3.connect(seeded)
        conn.execute(
            "INSERT INTO long_term_memory_items "
            "(memory_id, memory_type, statement_redacted, project_key, confidence_class, "
            " review_status) VALUES ('mem1','fact','kickoff confirmed','P1','high','accepted')"
        )
        conn.commit()
        conn.close()

        packet, assessment, retrieval_receipt_id, packet_receipt_id = build_research_packet(
            packet_type="interactive_query", project_key="P1", db_path=seeded, emit_receipt=True
        )

        empty = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty)  # migrate only
        blocked_packet, _, _, _ = build_research_packet(
            packet_type="interactive_query", project_key="P1", db_path=empty, emit_receipt=False
        )

        # Persisted row guard columns all 0.
        c2 = sqlite3.connect(seeded)
        c2.row_factory = sqlite3.Row
        row = dict(c2.execute("SELECT * FROM second_brain_research_packets").fetchone())
        c2.close()

    contract_fields = set(ResearchPacket.model_fields)
    blob = packet.model_dump_json() + assessment.model_dump_json()
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body", "raw_document_text", "raw_calendar_payload", "raw_prompt",
            "raw_response", "signed_url", "download_url", "secret",
        )
    )
    guards_zero = all(
        row[c] == 0
        for c in row
        if c.endswith("_persisted") or c in ("arbitrary_sql_allowed", "external_writeback_performed")
    )
    accepted_memory_present = any(
        r["source_family"] == "accepted_long_term_memory" for r in assessment.accepted_memory_refs
    )

    proof_passed = bool(
        retrieval_receipt_id
        and packet_receipt_id
        and packet.source_ref_count >= 1
        and {"packet_id", "topic_hash", "context_quality_class", "degradation_mode"} <= contract_fields
        and assessment.open_questions
        and accepted_memory_present
        and no_raw_content
        and guards_zero
        and blocked_packet.degradation_mode == "blocked"
        and blocked_packet.context_quality_class == "insufficient"
        and blocked_packet.status == "blocked"
    )
    return {
        "proof": "phase_08a_research_packet_agent",
        "proof_passed": proof_passed,
        "seeded_packet": {
            "source_ref_count": packet.source_ref_count,
            "context_quality_class": packet.context_quality_class,
            "degradation_mode": packet.degradation_mode,
            "review_tier": packet.review_tier,
            "families_present": assessment.families_present,
            "families_missing": assessment.families_missing,
            "source_coverage": assessment.source_coverage,
            "open_questions_count": len(assessment.open_questions),
            "accepted_memory_refs_count": len(assessment.accepted_memory_refs),
        },
        "empty_db_packet": {
            "degradation_mode": blocked_packet.degradation_mode,
            "context_quality_class": blocked_packet.context_quality_class,
            "status": blocked_packet.status,
        },
        "retrieval_receipt_linked": bool(retrieval_receipt_id),
        "packet_receipt_persisted": bool(packet_receipt_id),
        "guard_columns_zero": guards_zero,
        "no_raw_content": no_raw_content,
        "accepted_memory_present": accepted_memory_present,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "synthesis_requires_packet": True,
            "insufficient_context_degrades_not_overstates": True,
            "model_direct_external_api_access": False,
        },
    }
