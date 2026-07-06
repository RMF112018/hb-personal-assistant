"""Models, enums, deterministic identity, and normalization for the N8C-8 decision/preference/open-loop
memory layer.

Neutral and deterministic (no DB, no vault, no model). Enum tuples are re-exported from the V104 schema
module so the DB ``CHECK`` constraints and the Python layer can never drift. Text columns are hard-capped
here before the repository writes them — a record stores only bounded excerpts, never a raw source/email
body or a raw prompt/response.

Identity is deterministic and **lineage-scoped** so re-running the extractor is idempotent and
independent corroborating sources are never auto-obsoleted:
  * ``anchor_key`` = the first available STABLE provenance anchor
    (source_id → claim_id → pack_item_id → compilation_id → receipt_id → note_rel_path);
  * ``identity_key`` = sha256(kind | normalized_subject | normalized_action | anchor_key)[:24] — stable
    across evidence changes for the SAME lineage; different lineages get different identity keys;
  * the record id folds the evidence digest in (immutable-by-evidence) — a changed evidence digest
    yields a NEW record whose prior record (same identity_key) is superseded; a different source →
    different identity_key → coexists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_decision_memory_tables import (
    DECISION_MEMORY_EVENT_TYPE_VALUES,
    DECISION_MEMORY_RECORD_KIND_VALUES,
    DECISION_REVIEW_STATE_VALUES,
    DECISION_STATUS_VALUES,
    DECISION_TYPE_VALUES,
    OPEN_LOOP_PRIORITY_VALUES,
    OPEN_LOOP_STATUS_VALUES,
    OPEN_LOOP_TYPE_VALUES,
    PREFERENCE_STRENGTH_VALUES,
    PREFERENCE_TYPE_VALUES,
)

# Reuse the N8C-7 neutral helpers (single source of truth for normalization/bounding/hashing).
from .memory_models import (
    bound_text,
    clamp_confidence,
    sha256_hex,
)

# --- enum re-exports (single source of truth = the schema module) -----------------------
DECISION_TYPES = frozenset(DECISION_TYPE_VALUES)
PREFERENCE_TYPES = frozenset(PREFERENCE_TYPE_VALUES)
OPEN_LOOP_TYPES = frozenset(OPEN_LOOP_TYPE_VALUES)
DECISION_STATUSES = frozenset(DECISION_STATUS_VALUES)
OPEN_LOOP_STATUSES = frozenset(OPEN_LOOP_STATUS_VALUES)
REVIEW_STATES = frozenset(DECISION_REVIEW_STATE_VALUES)
PREFERENCE_STRENGTHS = frozenset(PREFERENCE_STRENGTH_VALUES)
OPEN_LOOP_PRIORITIES = frozenset(OPEN_LOOP_PRIORITY_VALUES)
RECORD_KINDS = frozenset(DECISION_MEMORY_RECORD_KIND_VALUES)
EVENT_TYPES = frozenset(DECISION_MEMORY_EVENT_TYPE_VALUES)

# Record kinds.
KIND_DECISION = "decision"
KIND_PREFERENCE = "preference"
KIND_OPEN_LOOP = "open_loop"

# Named decision types.
DECISION = "decision"
DECISION_CANDIDATE = "decision_candidate"
ARCHITECTURE_DECISION = "architecture_decision"

# Named preference types.
USER_PREFERENCE = "user_preference"
WORKFLOW_PREFERENCE = "workflow_preference"

# Named open-loop types.
OPEN_LOOP_COMMITMENT = "commitment"
OPEN_LOOP_TASK_CANDIDATE = "task_candidate"
OPEN_LOOP_QUESTION = "question"
OPEN_LOOP_RISK_FOLLOWUP = "risk_followup"
OPEN_LOOP_DECISION_NEEDED = "decision_needed"
OPEN_LOOP_WAITING_FOR = "waiting_for"

# Default advisory posture — NOTHING is auto-accepted.
STATUS_CANDIDATE = "candidate"
STATUS_SUPERSEDED = "superseded"
STATUS_STALE = "stale"
REVIEW_UNREVIEWED = "unreviewed"
REVIEW_NEEDS_REVIEW = "needs_review"

# Bump when the extraction/serialization contract changes — folded into the record ids via anchor/id.
EXTRACTOR_VERSION = "decision-memory-v1"

# --- hard caps --------------------------------------------------------------------------
TEXT_HARD_CAP = 500
EVIDENCE_HARD_CAP = 2_000
NORMALIZED_HARD_CAP = 300
LOW_CONFIDENCE = 0.4
QUESTION_CONFIDENCE_CAP = 0.35  # conservative — question heuristics are bounded + review-required
COMPILATION_CONFIDENCE_CAP = 0.4  # compilation-derived records are weak advisory


class DecisionMemoryValidationError(ValueError):
    """Raised on any structural/size/enum problem before a record is persisted."""


# --- deterministic identity -------------------------------------------------------------
# Stable provenance-anchor precedence: the first present wins, so a record keyed to a claim keeps a
# stable lineage even if source_id is absent.
_ANCHOR_ORDER = (
    "source_id", "claim_id", "pack_item_id", "compilation_id", "receipt_id", "note_rel_path",
)


def anchor_key(provenance: dict[str, Any]) -> str:
    """First available stable provenance anchor as ``field:value`` (robust when source_id is absent)."""
    for name in _ANCHOR_ORDER:
        val = provenance.get(name)
        if val:
            return f"{name}:{val}"
    return ""


def has_provenance(provenance: dict[str, Any]) -> bool:
    anchors = ("source_id", "note_rel_path", "claim_id", "memory_node_id", "memory_mention_id",
               "compilation_id", "pack_id", "pack_item_id", "receipt_id")
    return any(provenance.get(a) for a in anchors)


def compute_identity_key(kind: str, normalized_subject: str | None, normalized_action: str | None,
                         provenance: dict[str, Any], extra: str | None = None) -> str:
    """Stable lineage identity. ``extra`` folds a secondary discriminator (preference domain /
    open-loop type) INTO the identity so lineage-scoped supersede never obsoletes a genuinely different
    record — only a changed evidence digest for the SAME identity supersedes."""
    key = (f"{kind}|{normalized_subject or ''}|{normalized_action or ''}|{extra or ''}|"
           f"{anchor_key(provenance)}")
    return sha256_hex(key)[:24]


def compute_record_id(identity_key: str, evidence_digest: str | None) -> str:
    """Immutable-by-evidence id: same identity + same evidence → same id (idempotent); a changed
    evidence digest → a new id whose prior record (same identity_key) is superseded."""
    return sha256_hex(f"{identity_key}|{evidence_digest or ''}|{EXTRACTOR_VERSION}")[:24]


def _evidence_digest(evidence_excerpt: str | None, source_digest: str | None,
                     card_digest: str | None) -> str:
    """A stable digest of the record's evidence state — changing it means a new immutable record."""
    return sha256_hex(f"{evidence_excerpt or ''}|{source_digest or ''}|{card_digest or ''}")[:24]


# --- record drafts ----------------------------------------------------------------------
@dataclass
class _BaseRecord:
    normalized_subject: str | None = None
    domain: str | None = None
    confidence: float | None = None
    review_state: str = REVIEW_UNREVIEWED
    # provenance
    source_id: str | None = None
    note_rel_path: str | None = None
    claim_id: str | None = None
    memory_node_id: str | None = None
    memory_mention_id: str | None = None
    compilation_id: str | None = None
    pack_id: str | None = None
    pack_item_id: str | None = None
    receipt_id: str | None = None
    evidence_excerpt: str | None = None
    evidence_location: str | None = None
    source_digest: str | None = None
    card_digest: str | None = None
    observed_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def _provenance(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id, "note_rel_path": self.note_rel_path, "claim_id": self.claim_id,
            "memory_node_id": self.memory_node_id, "memory_mention_id": self.memory_mention_id,
            "compilation_id": self.compilation_id, "pack_id": self.pack_id,
            "pack_item_id": self.pack_item_id, "receipt_id": self.receipt_id,
        }

    def _base_row(self) -> dict[str, Any]:
        if not has_provenance(self._provenance()):
            raise DecisionMemoryValidationError("record_without_provenance")
        row = dict(self._provenance())
        row.update({
            "normalized_subject": bound_text(self.normalized_subject, NORMALIZED_HARD_CAP)
            if self.normalized_subject else None,
            "domain": self.domain,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "review_state": self.review_state,
            "evidence_excerpt": bound_text(self.evidence_excerpt, EVIDENCE_HARD_CAP)
            if self.evidence_excerpt else None,
            "evidence_location": self.evidence_location,
            "source_digest": self.source_digest, "card_digest": self.card_digest,
            "observed_at": self.observed_at, "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "metadata_json": _dump_metadata(self.metadata),
        })
        return row

    def _identity(self, kind: str, normalized_action: str | None,
                  extra: str | None = None) -> tuple[str, str]:
        identity = compute_identity_key(kind, self.normalized_subject, normalized_action,
                                        self._provenance(), extra=extra)
        digest = _evidence_digest(self.evidence_excerpt, self.source_digest, self.card_digest)
        return identity, digest


@dataclass
class DecisionRecord(_BaseRecord):
    decision_type: str = DECISION_CANDIDATE
    decision_text: str | None = None
    normalized_decision: str | None = None
    decided_at: str | None = None
    status: str = STATUS_CANDIDATE

    def to_row(self) -> dict[str, Any]:
        if self.decision_type not in DECISION_TYPES:
            raise DecisionMemoryValidationError(f"unknown_decision_type:{self.decision_type}")
        identity, digest = self._identity(KIND_DECISION, self.normalized_decision)
        row = self._base_row()
        row.update({
            "decision_id": compute_record_id(identity, digest),
            "identity_key": identity,
            "decision_type": self.decision_type,
            "decision_text": bound_text(self.decision_text, TEXT_HARD_CAP) if self.decision_text else None,
            "normalized_decision": bound_text(self.normalized_decision, NORMALIZED_HARD_CAP)
            if self.normalized_decision else None,
            "status": self.status,
            "decided_at": self.decided_at,
        })
        return row


@dataclass
class PreferenceRecord(_BaseRecord):
    preference_type: str = USER_PREFERENCE
    preference_text: str | None = None
    normalized_preference: str | None = None
    strength: str | None = None
    status: str = STATUS_CANDIDATE

    def to_row(self) -> dict[str, Any]:
        if self.preference_type not in PREFERENCE_TYPES:
            raise DecisionMemoryValidationError(f"unknown_preference_type:{self.preference_type}")
        # domain folds into the identity so a different-domain preference from the same lineage is a
        # distinct record (not a supersede target).
        identity, digest = self._identity(KIND_PREFERENCE, self.normalized_preference, extra=self.domain)
        row = self._base_row()
        row.update({
            "preference_id": compute_record_id(identity, digest),
            "identity_key": identity,
            "preference_type": self.preference_type,
            "preference_text": bound_text(self.preference_text, TEXT_HARD_CAP)
            if self.preference_text else None,
            "normalized_preference": bound_text(self.normalized_preference, NORMALIZED_HARD_CAP)
            if self.normalized_preference else None,
            "strength": self.strength,
            "status": self.status,
        })
        return row


@dataclass
class OpenLoopRecord(_BaseRecord):
    open_loop_type: str = OPEN_LOOP_TASK_CANDIDATE
    open_loop_text: str | None = None
    normalized_action: str | None = None
    priority: str | None = None
    due_at: str | None = None
    stale_after: str | None = None
    owner_hint: str | None = None
    status: str = STATUS_CANDIDATE

    def to_row(self) -> dict[str, Any]:
        if self.open_loop_type not in OPEN_LOOP_TYPES:
            raise DecisionMemoryValidationError(f"unknown_open_loop_type:{self.open_loop_type}")
        # open_loop_type folds into the identity so two loop kinds off one lineage are distinct records.
        identity, digest = self._identity(KIND_OPEN_LOOP, self.normalized_action,
                                          extra=self.open_loop_type)
        row = self._base_row()
        row.update({
            "open_loop_id": compute_record_id(identity, digest),
            "identity_key": identity,
            "open_loop_type": self.open_loop_type,
            "open_loop_text": bound_text(self.open_loop_text, TEXT_HARD_CAP)
            if self.open_loop_text else None,
            "normalized_action": bound_text(self.normalized_action, NORMALIZED_HARD_CAP)
            if self.normalized_action else None,
            "priority": self.priority,
            "status": self.status,
            "due_at": self.due_at,
            "stale_after": self.stale_after,
            "owner_hint": self.owner_hint,
        })
        return row


def _dump_metadata(metadata: dict[str, Any]) -> str | None:
    import json
    return json.dumps(metadata, sort_keys=True) if metadata else None
