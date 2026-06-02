"""Phase 08A long-term memory + operator preference structures (Prompt 10).

Compact, contract-conformant models aligned 1:1 with the V26 tables they persist to
(`memory_update_candidates`, `memory_update_reviews`, `long_term_memory_items` +
`_source_refs` + `_quality_signals`, `second_brain_operator_feedback`,
`second_brain_operator_preference_profiles`). Source refs / values are redacted metadata
only — never raw bodies, document text, calendar payloads, prompts, responses, URLs, or
secrets (rejected by a field validator mirroring the source-reference contract).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from ..reasoning import FORBIDDEN_REFERENCE_FIELDS

CandidateStatus = Literal["proposed", "accepted", "rejected", "superseded"]
ReviewDecision = Literal["accepted", "rejected", "superseded", "deferred"]
MemoryReviewStatus = Literal["accepted", "pending_review", "rejected", "superseded"]
QualitySignalType = Literal["origin", "provenance", "quality", "freshness", "conflict", "feedback"]
PreferenceScope = Literal["global", "project", "entity"]
FeedbackClass = Literal["accept", "reject", "correct", "prefer", "flag_review", "defer"]


def _reject_forbidden_refs(value: list[dict[str, str]]) -> list[dict[str, str]]:
    for ref in value:
        forbidden = set(ref) & FORBIDDEN_REFERENCE_FIELDS
        if forbidden:
            raise ValueError(f"forbidden raw field(s) in source_ref: {sorted(forbidden)}")
    return value


class MemoryCandidate(BaseModel):
    """A proposed long-term memory update (V26 ``memory_update_candidates``)."""

    candidate_id: str
    proposed_memory_type: str
    statement_redacted: str
    project_key: str | None = None
    origin_id: str | None = None
    provenance_class: str | None = None
    confidence_class: str = "unknown"
    review_required: bool = True
    review_tier: int = 3
    review_tier_reason_code: str = "T3_MODEL_ONLY"
    sensitivity_class: str = "normal"
    source_refs: list[dict[str, str]] = []
    status: CandidateStatus = "proposed"

    model_config = {"extra": "forbid"}

    @field_validator("review_tier")
    @classmethod
    def _tier_in_range(cls, value: int) -> int:
        if value not in (1, 2, 3):
            raise ValueError("review_tier must be 1, 2, or 3")
        return value

    _refs = field_validator("source_refs")(_reject_forbidden_refs)


class MemoryReview(BaseModel):
    """An operator review decision over a candidate (V26 ``memory_update_reviews``)."""

    review_id: str
    candidate_id: str
    decision: ReviewDecision
    reviewer_ref: str = "operator"
    decision_reason_redacted: str | None = None

    model_config = {"extra": "forbid"}


class MemoryItem(BaseModel):
    """An accepted long-term memory item (V26 ``long_term_memory_items``)."""

    memory_id: str
    memory_type: str
    statement_redacted: str
    project_key: str | None = None
    entity_key: str | None = None
    origin_id: str | None = None
    provenance_class: str | None = None
    confidence_class: str = "unknown"
    review_status: MemoryReviewStatus = "pending_review"
    sensitivity_class: str = "normal"
    supersedes_memory_id: str | None = None
    source_refs: list[dict[str, str]] = []

    model_config = {"extra": "forbid"}

    _refs = field_validator("source_refs")(_reject_forbidden_refs)


class QualitySignal(BaseModel):
    """A long-term memory quality signal (V26 ``long_term_memory_quality_signals``)."""

    signal_id: str
    memory_id: str
    signal_type: QualitySignalType
    origin_id: str | None = None
    provenance_class: str | None = None
    quality_score: float | None = None
    freshness_class: str | None = None
    conflict_flag: bool = False
    feedback_id: str | None = None
    review_required: bool = False

    model_config = {"extra": "forbid"}


class OperatorFeedback(BaseModel):
    """Auditable operator feedback (V26 ``second_brain_operator_feedback``)."""

    feedback_id: str
    target_kind: str
    target_id: str
    origin_id: str | None = None
    feedback_class: FeedbackClass = "accept"
    rating: int | None = None
    reason_redacted: str | None = None
    review_tier: int | None = None
    review_tier_reason_code: str | None = None

    model_config = {"extra": "forbid"}


class OperatorPreference(BaseModel):
    """A reviewable operator preference (V26 ``second_brain_operator_preference_profiles``).

    ``review_tier`` / ``review_tier_reason_code`` are advisory model-only metadata (the
    table stores ``review_status``); preferences are presentation-only and never override
    safety policy or review-tier routing.
    """

    preference_id: str
    scope: PreferenceScope = "global"
    scope_key: str | None = None
    preference_key: str
    preference_value_redacted: str | None = None
    confidence_class: str | None = None
    signal_count: int = 0
    source_feedback_refs: list[dict[str, str]] = []
    review_status: str = "pending_review"
    review_tier: int = 2
    review_tier_reason_code: str = "T2_STRONG_HEURISTIC"

    model_config = {"extra": "forbid"}

    _refs = field_validator("source_feedback_refs")(_reject_forbidden_refs)
