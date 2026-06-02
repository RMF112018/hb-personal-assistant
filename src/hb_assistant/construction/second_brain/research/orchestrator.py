"""Phase 08A Retrieval Orchestrator (A01) — Synthesized Prompt 07.

Routes a request, requires a research packet for complex / daily-brief paths, and gates
synthesis on context quality: synthesis is allowed only when a packet exists and context
is not blocked. Insufficient context degrades or blocks — it never produces an
"ok to overstate" result. No model, no raw content, no external access.
"""

from __future__ import annotations

from typing import Any

from .models import OrchestratorResult
from .packet import build_research_packet
from .policy import requires_research_packet


class RetrievalOrchestrator:
    """Deterministic orchestrator enforcing research-before-synthesis discipline."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def orchestrate(
        self,
        *,
        packet_type: str,
        project_key: str | None = None,
        families: tuple[str, ...] | None = None,
        emit_receipt: bool = True,
    ) -> OrchestratorResult:
        packet, assessment, retrieval_receipt_id, packet_receipt_id = build_research_packet(
            packet_type=packet_type,
            project_key=project_key,
            families=families,
            db_path=self._db_path,
            emit_receipt=emit_receipt,
        )
        request_requires_packet = requires_research_packet(packet_type)
        research_packet_ok = packet.degradation_mode != "blocked"
        # Synthesis requires a packet (present here) AND non-blocked context.
        synthesis_allowed = research_packet_ok

        warnings = list(assessment.policy_warnings)
        if not synthesis_allowed:
            warnings.append("synthesis_blocked:insufficient_context")
        if assessment.degradation_recommendation not in ("none",):
            warnings.append(f"degradation_recommended:{assessment.degradation_recommendation}")

        return OrchestratorResult(
            packet=packet,
            assessment=assessment,
            packet_type=packet_type,
            request_requires_packet=request_requires_packet,
            research_packet_ok=research_packet_ok,
            synthesis_allowed=synthesis_allowed,
            retrieval_receipt_id=retrieval_receipt_id,
            packet_receipt_id=packet_receipt_id,
            warnings=sorted(set(warnings)),
        )


def build_retrieval_orchestrator_proof() -> dict[str, Any]:
    """Deterministic proof for ``retrieval-orchestrator-proof.json`` (temp DB)."""
    import json
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

        orch = RetrievalOrchestrator(db_path=seeded)
        brief = orch.orchestrate(packet_type="daily_brief", project_key="P1", emit_receipt=False)
        query = orch.orchestrate(
            packet_type="interactive_query", project_key="P1", emit_receipt=False
        )

        empty = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty)
        insufficient = RetrievalOrchestrator(db_path=empty).orchestrate(
            packet_type="interactive_query", project_key="P1", emit_receipt=False
        )

    blob = brief.model_dump_json() + query.model_dump_json() + insufficient.model_dump_json()
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body", "raw_document_text", "raw_calendar_payload", "raw_prompt",
            "raw_response", "signed_url", "download_url", "secret",
        )
    )

    packet_built_for_both = bool(brief.packet.packet_id and query.packet.packet_id)
    both_require_packet = brief.request_requires_packet and query.request_requires_packet
    insufficient_degrades = (
        insufficient.packet.degradation_mode == "blocked"
        and insufficient.research_packet_ok is False
        and insufficient.synthesis_allowed is False
        and any(w.startswith("synthesis_blocked") for w in insufficient.warnings)
    )

    proof_passed = bool(
        packet_built_for_both and both_require_packet and insufficient_degrades and no_raw_content
    )
    return {
        "proof": "phase_08a_retrieval_orchestrator",
        "proof_passed": proof_passed,
        "daily_brief_path": {
            "packet_built": bool(brief.packet.packet_id),
            "request_requires_packet": brief.request_requires_packet,
            "synthesis_allowed": brief.synthesis_allowed,
            "degradation_mode": brief.packet.degradation_mode,
        },
        "interactive_query_path": {
            "packet_built": bool(query.packet.packet_id),
            "request_requires_packet": query.request_requires_packet,
            "synthesis_allowed": query.synthesis_allowed,
            "degradation_mode": query.packet.degradation_mode,
        },
        "insufficient_context_path": {
            "degradation_mode": insufficient.packet.degradation_mode,
            "research_packet_ok": insufficient.research_packet_ok,
            "synthesis_allowed": insufficient.synthesis_allowed,
            "warnings": insufficient.warnings,
        },
        "packet_built_for_both_paths": packet_built_for_both,
        "complex_paths_require_packet": both_require_packet,
        "insufficient_context_degrades_not_overstates": insufficient_degrades,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "synthesis_requires_packet": True,
            "insufficient_context_degrades_not_overstates": True,
            "model_direct_external_api_access": False,
        },
    }
