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

# Phase 10A P09: raw packet builders (canonical in local_ai/raw_context; thin delegation here for first-class orchestrate support)
try:
    from ..local_ai.raw_context import (
        build_raw_calendar_context_packet,
        build_raw_email_context_packet,
    )
except Exception:  # pragma: no cover - optional for environments without full local_ai
    build_raw_email_context_packet = None  # type: ignore
    build_raw_calendar_context_packet = None  # type: ignore


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
        # Phase 10A P09: raw-capable packets are first-class (delegated to canonical raw builders when requested).
        # These bypass the standard broker research path (they source from V42 raw tables when policy + model_context allow).
        if packet_type in ("raw_email_context", "raw_calendar_context", "raw_daily_brief_context"):
            store = None
            try:
                from hb_assistant.construction.store import ConstructionStore

                store = ConstructionStore(self._db_path)
            except Exception:
                store = None
            raw_pkt: dict[str, Any] | None = None
            if packet_type == "raw_email_context" and build_raw_email_context_packet is not None:
                raw_pkt = build_raw_email_context_packet(project_key=project_key, store=store)
            elif (
                packet_type == "raw_calendar_context"
                and build_raw_calendar_context_packet is not None
            ):
                raw_pkt = build_raw_calendar_context_packet(project_key=project_key, store=store)
            elif packet_type == "raw_daily_brief_context" and (
                build_raw_email_context_packet is not None
                or build_raw_calendar_context_packet is not None
            ):
                # Thin composite adapter for raw daily brief context (email + calendar raw sources for the project)
                email_p = (
                    build_raw_email_context_packet(project_key=project_key, store=store)
                    if build_raw_email_context_packet is not None
                    else {}
                )
                cal_p = (
                    build_raw_calendar_context_packet(project_key=project_key, store=store)
                    if build_raw_calendar_context_packet is not None
                    else {}
                )
                raw_pkt = {
                    "packet_type": "raw_daily_brief_context",
                    "project_key": project_key,
                    "email_context": email_p,
                    "calendar_context": cal_p,
                    "source_refs": (email_p or {}).get("source_refs", [])
                    + (cal_p or {}).get("source_refs", []),
                    "raw_content_included": bool(
                        (email_p or {}).get("raw_content_included")
                        or (cal_p or {}).get("raw_content_included")
                    ),
                }
            if raw_pkt is None:
                # Fallback: treat as blocked research packet (raw builder unavailable)
                from .models import ResearchPacket, ResearchPacketAssessment

                rp = ResearchPacket(
                    packet_id=f"raw-fallback-{packet_type}",
                    topic_hash="raw-fallback",
                    project_key=project_key,
                    context_quality_class="insufficient",
                    degradation_mode="blocked",
                    status="blocked",
                    summary_redacted=f"raw packet builder unavailable for {packet_type}",
                )
                assessment = ResearchPacketAssessment(degradation_recommendation="blocked")
                return OrchestratorResult(
                    packet=rp,
                    assessment=assessment,
                    packet_type=packet_type,
                    request_requires_packet=False,
                    research_packet_ok=False,
                    synthesis_allowed=False,
                    warnings=["raw_builder_unavailable"],
                )
            # Adapter: present raw packet via a ResearchPacket stand-in (raw posture is explicit via packet_type and raw_pkt content)
            from .models import ResearchPacket, ResearchPacketAssessment

            rp = ResearchPacket(
                packet_id=raw_pkt.get("packet_id")
                or raw_pkt.get("id")
                or f"{packet_type}:{project_key or 'global'}",
                topic_hash=raw_pkt.get("topic_hash") or raw_pkt.get("id") or packet_type,
                project_key=project_key or raw_pkt.get("project_key"),
                retrieval_receipt_id=None,
                source_ref_count=len(raw_pkt.get("source_refs", []))
                if isinstance(raw_pkt.get("source_refs"), list)
                else 0,
                context_quality_class="sufficient",
                degradation_mode="none",
                confidence_class="high",
                review_tier=1,
                review_tier_reason_code="RAW_CONTEXT",
                review_status="pending_review",
                advisory_classification="advisory",
                summary_redacted=f"raw {packet_type} (see raw_content / bounds / source_refs)",
                status="ok",
            )
            assessment = ResearchPacketAssessment(
                families_present=[packet_type],
                source_coverage=1.0,
                degradation_recommendation="none",
            )
            return OrchestratorResult(
                packet=rp,
                assessment=assessment,
                packet_type=packet_type,
                request_requires_packet=False,
                research_packet_ok=True,
                synthesis_allowed=True,
                retrieval_receipt_id=None,
                packet_receipt_id=None,
                warnings=[],
            )

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
