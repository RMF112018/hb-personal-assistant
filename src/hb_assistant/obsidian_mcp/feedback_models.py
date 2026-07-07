"""N8C-18 feedback models: deterministic identity, bounded caps, and the advisory-recommendation derivation.

Neutral and deterministic (no DB, no vault, no model, NO LLM, no network). Defines the bounded
``FeedbackTarget`` / ``FeedbackRecommendation`` payloads, the fixed no-execution / feedback-only /
advisory-review-loop policy constants, deterministic ids, and a conservative deterministic mapping from a
feedback type to an ADVISORY review-loop recommendation. It NEVER executes an action, stages anything,
writes a review disposition, mutates a source/workflow record, or generates a final answer.

A feedback ``feedback_id`` is deterministic (folded from the feedback type + sorted target signatures +
bounded note + author + builder version), so re-submitting identical feedback dedupes to the same record
rather than creating a duplicate. A recommendation is ALWAYS advisory: it suggests a review-loop action for
an operator, it never applies one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_feedback_tables import (
    FEEDBACK_EVENT_TYPE_VALUES,
    FEEDBACK_STATUS_VALUES,
    FEEDBACK_TARGET_KIND_VALUES,
    FEEDBACK_TYPE_VALUES,
    RECOMMENDATION_TYPE_VALUES,
)

from .memory_models import bound_text, sha256_hex

# Bump when the feedback-build / serialization contract changes — folded into every id.
FEEDBACK_BUILDER_VERSION = "feedback-v1"

FEEDBACK_TYPES = frozenset(FEEDBACK_TYPE_VALUES)
FEEDBACK_TARGET_KINDS = frozenset(FEEDBACK_TARGET_KIND_VALUES)
FEEDBACK_STATUSES = frozenset(FEEDBACK_STATUS_VALUES)
RECOMMENDATION_TYPES = frozenset(RECOMMENDATION_TYPE_VALUES)
EVENT_TYPES = frozenset(FEEDBACK_EVENT_TYPE_VALUES)

# --- fixed policy constants (never overridable; pinned by schema CHECK + asserted by tests) --------------
ACTION_POLICY = "no_execution"
EXECUTION_POLICY = "feedback_only"
REVIEW_POLICY = "advisory_review_loop"
SOURCE_POLICY = "preserve_source_truth"
CITATION_POLICY = "preserve_citations"

FEEDBACK_POLICY_BLOCK = {
    "action_policy": ACTION_POLICY,
    "execution_policy": EXECUTION_POLICY,
    "review_policy": REVIEW_POLICY,
    "source_policy": SOURCE_POLICY,
    "citation_policy": CITATION_POLICY,
    "requires_operator_review": 1,
}

# --- bounded hard caps ----------------------------------------------------------------------------------
NOTE_HARD_CAP = 2_000
RATIONALE_HARD_CAP = 500
LABEL_HARD_CAP = 200
ID_HARD_CAP = 200
REF_HARD_CAP = 500
MAX_TARGETS = 50
MAX_RECOMMENDATIONS = 50

# Optional typed upstream anchors a target may carry (in addition to the mandatory target_kind + target_id).
TARGET_ANCHOR_FIELDS: tuple[str, ...] = (
    "workflow_id", "workflow_type", "workflow_section", "draft_id", "draft_section_id", "packet_id",
    "packet_item_id", "projection_id", "projection_item_id", "context_pack_id", "memory_node_id",
    "memory_mention_id", "decision_id", "preference_id", "open_loop_id", "review_item_id", "claim_id",
    "citation_id", "source_id", "source_ref", "source_root_key", "rel_path", "note_rel_path",
)


class FeedbackValidationError(ValueError):
    """Raised on a structural/enum/size problem building a feedback record."""


def canonical_json(obj: Any) -> str:
    """Deterministic JSON (sorted keys) for digests folded into feedback ids."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"), default=str)


def _clean_id(value: Any, cap: int = ID_HARD_CAP) -> str | None:
    if value is None:
        return None
    text = bound_text(str(value).strip(), cap)
    return text or None


# --- payload dataclasses --------------------------------------------------------------------------------
@dataclass
class FeedbackTarget:
    """One artifact a feedback record is about, with preserved provenance (bounded ids only, no body)."""

    target_kind: str
    target_id: str
    target_label: str | None = None
    anchors: dict[str, Any] = field(default_factory=dict)
    target_digest: str | None = None
    review_state: str | None = None
    effective_state: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_anchors(self) -> dict[str, str]:
        """Only whitelisted, bounded anchor ids (drops anything unknown / non-scalar)."""
        out: dict[str, str] = {}
        for name in TARGET_ANCHOR_FIELDS:
            val = _clean_id(self.anchors.get(name), REF_HARD_CAP)
            if val:
                out[name] = val
        return out

    def signature(self) -> str:
        """Deterministic identity signature: kind + id + sorted anchors."""
        anchors = ";".join(f"{k}={v}" for k, v in sorted(self.normalized_anchors().items()))
        return f"{self.target_kind}|{self.target_id}|{anchors}"

    def to_row(self, feedback_id: str, order: int) -> dict[str, Any]:
        if self.target_kind not in FEEDBACK_TARGET_KINDS:
            raise FeedbackValidationError(f"unknown_target_kind:{self.target_kind}")
        tid = _clean_id(self.target_id)
        if not tid:
            raise FeedbackValidationError("feedback_target_requires_target_id")
        row: dict[str, Any] = {
            "feedback_target_id": compute_feedback_target_id(feedback_id, self.target_kind, tid, order),
            "feedback_id": feedback_id,
            "target_order": int(order),
            "target_kind": self.target_kind,
            "target_id": tid,
            "target_label": bound_text(self.target_label, LABEL_HARD_CAP) or None,
            "target_digest": _clean_id(self.target_digest, REF_HARD_CAP),
            "review_state": self.review_state or None,
            "effective_state": self.effective_state or None,
            "metadata_json": canonical_json(self.metadata) if self.metadata else None,
        }
        row.update(self.normalized_anchors())
        return row


@dataclass
class FeedbackRecommendation:
    """A deterministic ADVISORY review-loop recommendation derived from a feedback record."""

    recommendation_type: str
    target_kind: str | None = None
    target_id: str | None = None
    rationale: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_row(self, feedback_id: str, order: int) -> dict[str, Any]:
        if self.recommendation_type not in RECOMMENDATION_TYPES:
            raise FeedbackValidationError(f"unknown_recommendation_type:{self.recommendation_type}")
        return {
            "recommendation_id": compute_recommendation_id(
                feedback_id, self.recommendation_type, self.target_kind, self.target_id, order),
            "feedback_id": feedback_id,
            "recommendation_order": int(order),
            "recommendation_type": self.recommendation_type,
            "target_kind": self.target_kind or None,
            "target_id": _clean_id(self.target_id),
            "rationale": bound_text(self.rationale, RATIONALE_HARD_CAP) or None,
            "review_policy": REVIEW_POLICY,
            "requires_operator_review": 1,
            "metadata_json": canonical_json(self.metadata) if self.metadata else None,
        }


# --- deterministic identity -----------------------------------------------------------------------------
def compute_feedback_input_digest(feedback_type: str, target_signatures: list[str], note: str | None,
                                  created_by: str | None) -> str:
    joined = "|".join(sorted(target_signatures))
    note_digest = sha256_hex(bound_text(note, NOTE_HARD_CAP))[:16]
    return sha256_hex(f"{feedback_type}#{joined}#note={note_digest}#by={created_by or ''}")[:24]


def compute_feedback_output_digest(target_ids: list[str], recommendation_ids: list[str]) -> str:
    return sha256_hex(f"{'|'.join(sorted(target_ids))}#{'|'.join(sorted(recommendation_ids))}")[:24]


def compute_feedback_id(feedback_type: str, target_signatures: list[str], note: str | None,
                        created_by: str | None) -> str:
    """Deterministic + idempotent: identical (type, targets, note, author) → same feedback_id."""
    input_digest = compute_feedback_input_digest(feedback_type, target_signatures, note, created_by)
    return sha256_hex(f"{feedback_type}|{input_digest}|{FEEDBACK_BUILDER_VERSION}")[:24]


def compute_feedback_target_id(feedback_id: str, target_kind: str, target_id: str, order: int) -> str:
    return sha256_hex(f"{feedback_id}|{target_kind}|{target_id}|{int(order)}")[:24]


def compute_recommendation_id(feedback_id: str, recommendation_type: str, target_kind: str | None,
                              target_id: str | None, order: int) -> str:
    return sha256_hex(
        f"{feedback_id}|{recommendation_type}|{target_kind or ''}|{target_id or ''}|{int(order)}")[:24]


def compute_feedback_receipt_id(feedback_id: str, input_digest: str, output_digest: str) -> str:
    return sha256_hex(f"{feedback_id}|{input_digest}|{output_digest}|{FEEDBACK_BUILDER_VERSION}")[:24]


# --- deterministic advisory recommendation derivation ---------------------------------------------------
# feedback_type → advisory recommendation_type. Every value is a SUGGESTION for the operator's review loop —
# NEVER an applied relabel/accept/reject/defer/dispose. ``useful`` produces no recommendation (positive
# signal, nothing to review).
_RECOMMENDATION_MAP: dict[str, str] = {
    "not_useful": "suggest_more_context",
    "incorrect": "suggest_review",
    "incomplete": "suggest_more_context",
    "needs_review": "suggest_review",
    "needs_more_context": "suggest_more_context",
    "wrong_source": "suggest_source_check",
    "missing_source": "suggest_source_check",
    "wrong_review_label": "suggest_review",
    "candidate_should_be_trusted": "suggest_relabel_trusted",
    "trusted_should_be_candidate": "suggest_relabel_candidate",
    "should_be_excluded": "suggest_exclude",
    "duplicate": "suggest_deduplicate",
    "stale": "suggest_review",
    "operator_note": "operator_note",
    "unknown": "operator_note",
}


def derive_recommendations(feedback_type: str, targets: list[FeedbackTarget]) -> list[FeedbackRecommendation]:
    """Deterministic ADVISORY recommendation(s) for a feedback record. One recommendation of the mapped type,
    anchored to the primary (first) target. ``useful`` and unmapped types → no recommendation."""
    rec_type = _RECOMMENDATION_MAP.get(feedback_type)
    if not rec_type:
        return []
    primary = targets[0] if targets else None
    rationale = (f"Operator feedback '{feedback_type}' advises {rec_type} for operator review. "
                 "Advisory only — no state is changed.")
    return [FeedbackRecommendation(
        recommendation_type=rec_type,
        target_kind=primary.target_kind if primary else None,
        target_id=primary.target_id if primary else None,
        rationale=rationale,
    )]
