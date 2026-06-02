"""Phase 08A retrieval envelope structures (Synthesized Prompt 04).

The Retrieval and Source Broker Agent (A03) returns a `RetrievalEnvelope` of
bounded, redacted, source-linked `RetrievalItem`s. No raw bodies, signed/download
URLs, secrets, prompts, or model responses — enforced by a field validator that
rejects the forbidden raw reference fields. Items map into the adapter's
`ContextEnvelope` via `to_context_envelope`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from ..reasoning import FORBIDDEN_REFERENCE_FIELDS, ContextEnvelope

ReviewTier = Literal[1, 2, 3]
DegradationMode = Literal[
    "none", "narrow_claims", "advisory_only", "ask_for_targeted_research", "blocked"
]


class RetrievalItem(BaseModel):
    """One bounded, source-linked retrieved record (metadata + redacted excerpt)."""

    source_family: str
    source_ref: str
    record_type: str
    record_ref: str
    project_key: str | None = None
    confidence_class: str = "unknown"
    review_tier: int = 3
    review_status: str = "review_required"
    review_required: bool = True
    relationship_state: str | None = None
    evidence_ref: str | None = None
    stale_unknown_flags: list[str] = []
    conflict_flags: list[str] = []
    content_excerpt_redacted: str = ""
    recency: str = ""
    allowed_for_model_context: bool = True

    model_config = {"extra": "forbid"}

    @field_validator("review_tier")
    @classmethod
    def _tier_in_range(cls, value: int) -> int:
        if value not in (1, 2, 3):
            raise ValueError("review_tier must be 1, 2, or 3")
        return value

    @field_validator("source_family", "source_ref", "record_type", "record_ref")
    @classmethod
    def _no_forbidden_field_name(cls, value: str) -> str:
        if value in FORBIDDEN_REFERENCE_FIELDS:
            raise ValueError(f"forbidden raw field name in retrieval item: {value!r}")
        return value


class RetrievalEnvelope(BaseModel):
    """Bounded retrieval output: items + budget accounting + warnings."""

    items: list[RetrievalItem] = []
    degradation_mode: DegradationMode = "blocked"
    context_char_count: int = 0
    truncated: bool = False
    tier_distribution: dict[str, int] = {}
    coverage_warnings: list[str] = []
    stale_unknown_warnings: list[str] = []
    conflict_warnings: list[str] = []
    project_key: str | None = None
    query_hash: str | None = None

    model_config = {"extra": "forbid"}

    def to_context_envelope(self, *, question: str) -> ContextEnvelope:
        """Map into the adapter's bounded ContextEnvelope (safe fields only)."""
        source_references = [
            {
                "source_family": it.source_family,
                "source_ref": it.source_ref,
                "record_type": it.record_type,
                "record_ref": it.record_ref,
                "confidence_class": it.confidence_class,
                "review_tier": str(it.review_tier),
            }
            for it in self.items
        ]
        # Most-restrictive review tier present (3 > 2 > 1); default 3 if empty.
        tier = max((it.review_tier for it in self.items), default=3)
        reason = "T3_MODEL_ONLY" if tier == 3 else "T1_DETERMINISTIC_SOURCE_BACKED"
        if self.items and not self.truncated and self.degradation_mode == "none":
            quality: Literal["sufficient", "partial", "insufficient"] = "sufficient"
        elif self.items:
            quality = "partial"
        else:
            quality = "insufficient"
        return ContextEnvelope(
            question=question,
            source_references=source_references,
            review_tier=tier,
            review_reason_code=reason,
            confidence_class="low" if tier == 3 else "medium",
            research_packet_ok=False,
            context_quality=quality,
            disposition="advisory",
            coverage_warnings=self.coverage_warnings,
            stale_unknown_warnings=self.stale_unknown_warnings,
            conflict_warnings=self.conflict_warnings,
        )
