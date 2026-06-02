"""Phase 08A research-packet + orchestrator structures (Prompt 07).

`ResearchPacket` is the compact, contract-conformant pre-synthesis assessment that is
persisted (1:1 with the V26 ``second_brain_research_packets`` columns and the repo
``research_packet_contract`` required_fields). `ResearchPacketAssessment` is the richer
computed view (source coverage detail, open questions, accepted-memory refs) returned to
callers but not persisted raw. `OrchestratorResult` is the orchestrator's gating output.
No raw bodies/document text/calendar payloads/prompts/responses/URLs/secrets — ever.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from ..reasoning import FORBIDDEN_REFERENCE_FIELDS

ContextQualityClass = Literal["sufficient", "partial", "insufficient"]
# Research-packet (contract) degradation vocabulary — 3-value.
PacketDegradationMode = Literal["none", "graceful_degraded", "blocked"]
# Retrieval-broker (actionable recommendation) vocabulary — 5-value.
DegradationRecommendation = Literal[
    "none", "narrow_claims", "advisory_only", "ask_for_targeted_research", "blocked"
]


class ResearchPacket(BaseModel):
    """Compact, contract-conformant research packet (persisted to V26)."""

    packet_id: str
    topic_hash: str
    project_key: str | None = None
    retrieval_receipt_id: str | None = None
    source_ref_count: int = 0
    review_required_count: int = 0
    stale_unknown_count: int = 0
    conflict_count: int = 0
    context_quality_class: ContextQualityClass = "insufficient"
    degradation_mode: PacketDegradationMode = "blocked"
    confidence_class: str = "low"
    review_tier: int = 3
    review_tier_reason_code: str = "T3_MANDATORY_REVIEW"
    review_status: str = "pending_review"
    advisory_classification: str = "advisory"
    coverage_warnings: list[str] = []
    summary_redacted: str = ""
    status: str = "blocked"

    model_config = {"extra": "forbid"}

    @field_validator("review_tier")
    @classmethod
    def _tier_in_range(cls, value: int) -> int:
        if value not in (1, 2, 3):
            raise ValueError("review_tier must be 1, 2, or 3")
        return value


class ResearchPacketAssessment(BaseModel):
    """Richer computed pre-synthesis view (returned, not persisted raw)."""

    families_present: list[str] = []
    families_missing: list[str] = []
    source_coverage: float = 0.0
    source_ref_completeness: float = 0.0
    review_tier_distribution: dict[str, int] = {}
    stale_unknown_count: int = 0
    conflict_count: int = 0
    accepted_memory_refs: list[dict[str, str]] = []
    open_questions: list[str] = []
    policy_warnings: list[str] = []
    degradation_recommendation: DegradationRecommendation = "blocked"

    model_config = {"extra": "forbid"}

    @field_validator("accepted_memory_refs")
    @classmethod
    def _refs_have_no_forbidden_fields(
        cls, value: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        for ref in value:
            forbidden = set(ref) & FORBIDDEN_REFERENCE_FIELDS
            if forbidden:
                raise ValueError(f"forbidden raw field(s) in memory_ref: {sorted(forbidden)}")
        return value


class OrchestratorResult(BaseModel):
    """Orchestrator (A01) routing + gating output."""

    packet: ResearchPacket
    assessment: ResearchPacketAssessment
    packet_type: str
    request_requires_packet: bool
    research_packet_ok: bool
    synthesis_allowed: bool
    retrieval_receipt_id: str | None = None
    packet_receipt_id: str | None = None
    warnings: list[str] = []

    model_config = {"extra": "forbid"}
