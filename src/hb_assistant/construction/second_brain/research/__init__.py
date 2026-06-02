"""Phase 08A Retrieval Orchestrator (A01) + Research Packet Agent (A02) — Prompt 07.

Pre-synthesis context-quality gate: the research packet agent assesses source coverage,
stale/unknowns, conflicts, review-tier density, accepted memory, and open questions, and
recommends graceful degradation; the orchestrator requires a packet for complex / daily-
brief paths and gates synthesis so insufficient context degrades or blocks (never
overstates). Deterministic, local-first, read-only, metadata-only receipts.
"""

from __future__ import annotations

from .models import (
    OrchestratorResult,
    ResearchPacket,
    ResearchPacketAssessment,
)
from .orchestrator import RetrievalOrchestrator, build_retrieval_orchestrator_proof
from .packet import (
    build_research_packet,
    build_research_packet_agent_proof,
    build_research_packet_from_envelope,
)
from .policy import (
    PACKET_TYPES,
    ResearchPacketPolicyError,
    load_research_packet_policy_seed,
    requires_research_packet,
    score_context_quality,
    validate_research_packet_policy,
)
from .store import read_latest_research_packets, write_research_packet_receipt

__all__ = [
    "OrchestratorResult",
    "ResearchPacket",
    "ResearchPacketAssessment",
    "RetrievalOrchestrator",
    "build_retrieval_orchestrator_proof",
    "build_research_packet",
    "build_research_packet_agent_proof",
    "build_research_packet_from_envelope",
    "PACKET_TYPES",
    "ResearchPacketPolicyError",
    "load_research_packet_policy_seed",
    "requires_research_packet",
    "score_context_quality",
    "validate_research_packet_policy",
    "read_latest_research_packets",
    "write_research_packet_receipt",
]
