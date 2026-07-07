"""Models, enums, deterministic identity, and normalization for the N8C-9 review-overlay layer.

Neutral and deterministic (no DB, no vault, no model). Enum tuples are re-exported from the V105 schema
module so the DB ``CHECK`` constraints and the Python layer can never drift. Text columns are hard-capped
here before the repository writes them — a review item stores only BOUNDED metadata (target ids + digests
+ bounded title/summary/evidence_excerpt), never a raw source/email body, a full enrichment
``result_json``, a full context-pack export, a full memory compilation, or a raw prompt/response.

Two deterministic identities, with deliberately different idempotency semantics:
  * ``review_item_id`` = sha256(target_kind | target_id | target_digest | review_type |
    REVIEW_BUILDER_VERSION)[:24] — STABLE, so rebuilding the queue over unchanged advisory records is
    idempotent (no duplicate). A changed ``target_digest`` yields a NEW review_item_id whose prior item
    (same target_kind+target_id+review_type lineage) is marked ``superseded`` by the repository.
  * ``disposition_id`` = sha256(review_item_id | disposition_type | to_review_state | to_effective_state |
    operator_id | reason_digest | created_at_nonce)[:24] — EVENT-UNIQUE (folds a timestamp/nonce), because
    the disposition ledger is append-only: recording a decision must never silently overwrite a prior one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_review_tables import (
    DISPOSITION_TYPE_VALUES,
    EFFECTIVE_STATE_VALUES,
    REVIEW_EVENT_TYPE_VALUES,
    REVIEW_STATE_VALUES,
    REVIEW_TARGET_KIND_VALUES,
    REVIEW_TYPE_VALUES,
)

# Reuse the N8C-7 neutral helpers (single source of truth for bounding/hashing).
from .memory_models import bound_text, clamp_confidence, sha256_hex

# --- enum re-exports (single source of truth = the schema module) -----------------------
TARGET_KINDS = frozenset(REVIEW_TARGET_KIND_VALUES)
REVIEW_TYPES = frozenset(REVIEW_TYPE_VALUES)
REVIEW_STATES = frozenset(REVIEW_STATE_VALUES)
EFFECTIVE_STATES = frozenset(EFFECTIVE_STATE_VALUES)
DISPOSITION_TYPES = frozenset(DISPOSITION_TYPE_VALUES)
EVENT_TYPES = frozenset(REVIEW_EVENT_TYPE_VALUES)

# Default advisory posture — NOTHING is auto-accepted.
REVIEW_UNREVIEWED = "unreviewed"
REVIEW_NEEDS_REVIEW = "needs_review"
STATE_CANDIDATE = "candidate"
STATE_STALE = "stale"
STATE_SUPERSEDED = "superseded"
REVIEW_STALE = "stale"
REVIEW_SUPERSEDED = "superseded"

# Bump when the review-build / serialization contract changes — folded into the review_item_id.
REVIEW_BUILDER_VERSION = "review-queue-v1"

# --- hard caps --------------------------------------------------------------------------
TITLE_HARD_CAP = 300
SUMMARY_HARD_CAP = 500
EVIDENCE_HARD_CAP = 2_000
REASON_HARD_CAP = 500
NOTE_HARD_CAP = 500

# Disposition → (review_state, effective_state). The single source of truth for effective-state mapping.
DISPOSITION_STATE_MAP: dict[str, tuple[str, str]] = {
    "accept": ("operator_accepted", "accepted"),
    "reject": ("operator_rejected", "rejected"),
    "defer": ("deferred", "deferred"),
    "mark_not_required": ("not_required", "not_required"),
    "mark_stale": ("stale", "stale"),
    "mark_superseded": ("superseded", "superseded"),
    "request_more_context": ("needs_review", "candidate"),
}


class ReviewValidationError(ValueError):
    """Raised on any structural/size/enum problem before a review row is persisted."""


# Provenance anchors (in addition to the always-present ``target_id``).
_ANCHORS = (
    "source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
    "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id",
    "open_loop_id",
)


def has_provenance(provenance: dict[str, Any]) -> bool:
    return any(provenance.get(a) for a in _ANCHORS)


def compute_review_item_id(target_kind: str, target_id: str, target_digest: str | None,
                           review_type: str) -> str:
    """Stable review-item identity: same target + digest + review_type → same id (idempotent rebuild).
    A changed ``target_digest`` yields a new id; the prior item of the same lineage is superseded."""
    key = f"{target_kind}|{target_id}|{target_digest or ''}|{review_type}|{REVIEW_BUILDER_VERSION}"
    return sha256_hex(key)[:24]


def compute_disposition_id(review_item_id: str, disposition_type: str, to_review_state: str,
                           to_effective_state: str, operator_id: str | None, reason: str | None,
                           created_at_nonce: str) -> str:
    """Event-unique disposition identity: folds a timestamp/nonce so the append-only ledger never
    collapses two distinct decisions into one row."""
    reason_digest = sha256_hex(reason or "")[:16]
    key = (f"{review_item_id}|{disposition_type}|{to_review_state}|{to_effective_state}|"
           f"{operator_id or ''}|{reason_digest}|{created_at_nonce}")
    return sha256_hex(key)[:24]


def disposition_states(disposition_type: str) -> tuple[str, str]:
    """(review_state, effective_state) a disposition_type maps to. Raises on unknown."""
    if disposition_type not in DISPOSITION_STATE_MAP:
        raise ReviewValidationError(f"unknown_disposition_type:{disposition_type}")
    return DISPOSITION_STATE_MAP[disposition_type]


# --- review item draft ------------------------------------------------------------------
@dataclass
class ReviewItem:
    target_kind: str
    target_id: str
    review_type: str
    target_digest: str | None = None
    target_state_digest: str | None = None
    title: str | None = None
    summary: str | None = None
    review_state: str = REVIEW_UNREVIEWED
    effective_state: str = STATE_CANDIDATE
    confidence: float | None = None
    priority: str | None = None
    stale: bool = False
    superseded: bool = False
    # provenance
    source_id: str | None = None
    note_rel_path: str | None = None
    claim_id: str | None = None
    receipt_id: str | None = None
    pack_id: str | None = None
    pack_item_id: str | None = None
    memory_node_id: str | None = None
    memory_mention_id: str | None = None
    compilation_id: str | None = None
    decision_id: str | None = None
    preference_id: str | None = None
    open_loop_id: str | None = None
    evidence_excerpt: str | None = None
    evidence_location: str | None = None
    source_digest: str | None = None
    card_digest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def _provenance(self) -> dict[str, Any]:
        return {a: getattr(self, a) for a in _ANCHORS}

    def to_row(self) -> dict[str, Any]:
        if self.target_kind not in TARGET_KINDS:
            raise ReviewValidationError(f"unknown_target_kind:{self.target_kind}")
        if self.review_type not in REVIEW_TYPES:
            raise ReviewValidationError(f"unknown_review_type:{self.review_type}")
        if self.review_state not in REVIEW_STATES:
            raise ReviewValidationError(f"unknown_review_state:{self.review_state}")
        if self.effective_state not in EFFECTIVE_STATES:
            raise ReviewValidationError(f"unknown_effective_state:{self.effective_state}")
        if not self.target_id:
            raise ReviewValidationError("review_item_without_target_id")
        if not has_provenance(self._provenance()):
            raise ReviewValidationError("review_item_without_provenance")
        row = dict(self._provenance())
        row.update({
            "review_item_id": compute_review_item_id(self.target_kind, self.target_id,
                                                     self.target_digest, self.review_type),
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "target_digest": self.target_digest,
            "target_state_digest": self.target_state_digest,
            "review_type": self.review_type,
            "title": bound_text(self.title, TITLE_HARD_CAP) if self.title else None,
            "summary": bound_text(self.summary, SUMMARY_HARD_CAP) if self.summary else None,
            "review_state": self.review_state,
            "effective_state": self.effective_state,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "priority": self.priority,
            "stale": 1 if self.stale else 0,
            "superseded": 1 if self.superseded else 0,
            "evidence_excerpt": bound_text(self.evidence_excerpt, EVIDENCE_HARD_CAP)
            if self.evidence_excerpt else None,
            "evidence_location": self.evidence_location,
            "source_digest": self.source_digest,
            "card_digest": self.card_digest,
            "metadata_json": _dump_metadata(self.metadata),
        })
        return row


def _dump_metadata(metadata: dict[str, Any]) -> str | None:
    import json
    return json.dumps(metadata, sort_keys=True) if metadata else None
