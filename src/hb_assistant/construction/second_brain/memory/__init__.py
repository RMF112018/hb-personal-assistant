"""Phase 08A Memory Curator (A07) + Operator Preference (A08) agents — Prompt 10.

Source-linked, review-controlled long-term memory: candidates carry origin + source refs +
quality signals + review tier; sensitive/high-impact material routes to Tier 3 and is never
auto-accepted; promotion to accepted memory happens only via an explicit operator review.
Operator preferences are reviewable, presentation-only records that can never override
safety policy / review-tier routing. Metadata-only; no raw content; dry-run-first.
"""

from __future__ import annotations

from .curator import (
    build_long_term_memory_proof,
    build_memory_curator_agent_proof,
    propose_memory_candidate,
    review_memory_candidate,
)
from .models import (
    MemoryCandidate,
    MemoryItem,
    MemoryReview,
    OperatorFeedback,
    OperatorPreference,
    QualitySignal,
)
from .policy import (
    MemoryPolicyError,
    apply_operator_preferences,
    classify_memory_tier,
    classify_preference,
    load_memory_policy_seed,
    load_operator_preference_policy_seed,
    sensitive_high_impact_categories,
    validate_memory_policy,
)
from .preference import (
    build_operator_preference_proof,
    capture_preference,
    record_operator_feedback,
)

__all__ = [
    "build_long_term_memory_proof",
    "build_memory_curator_agent_proof",
    "propose_memory_candidate",
    "review_memory_candidate",
    "MemoryCandidate",
    "MemoryItem",
    "MemoryReview",
    "OperatorFeedback",
    "OperatorPreference",
    "QualitySignal",
    "MemoryPolicyError",
    "apply_operator_preferences",
    "classify_memory_tier",
    "classify_preference",
    "load_memory_policy_seed",
    "load_operator_preference_policy_seed",
    "sensitive_high_impact_categories",
    "validate_memory_policy",
    "build_operator_preference_proof",
    "capture_preference",
    "record_operator_feedback",
]
