"""Models, enums, deterministic identity, budget, and inclusion classification for the N8C-10
review-aware intelligence projection layer.

Neutral and deterministic (no DB, no vault, no model). Enum tuples are re-exported from the V106 schema
module so DB ``CHECK`` constraints and the Python layer can never drift. Text columns are hard-capped
before the repository writes them — a projection item stores only BOUNDED metadata (ids/digests/state +
bounded title/summary/evidence_excerpt), never a raw source/card/vault body, a full enrichment
``result_json``, a full context-pack export, a full memory compilation, a full review-item payload, or a
raw prompt/response.

A projection is a materialized READ product. Effective review state is READ from the N8C-9 review overlay
and classified into an ``inclusion_state`` per the projection type's policy — it NEVER converts a
candidate record into accepted truth. Determinism makes rebuilds idempotent; a changed effective state
(new disposition) changes ``input_digest`` and yields a new ``projection_id`` (the prior projection of the
same type+scope is marked stale/superseded by the repository — a projection-owned row only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_intelligence_projection_tables import (
    INCLUSION_STATE_VALUES,
    PROJECTION_EVENT_TYPE_VALUES,
    PROJECTION_STATUS_VALUES,
    PROJECTION_TYPE_VALUES,
)

from .memory_models import bound_text, clamp_confidence, sha256_hex

# --- enum re-exports (single source of truth = the schema module) -----------------------
PROJECTION_TYPES = frozenset(PROJECTION_TYPE_VALUES)
PROJECTION_STATUSES = frozenset(PROJECTION_STATUS_VALUES)
INCLUSION_STATES = frozenset(INCLUSION_STATE_VALUES)
EVENT_TYPES = frozenset(PROJECTION_EVENT_TYPE_VALUES)

# Named projection types.
TRUSTED_CONTEXT = "trusted_context"
CANDIDATE_CONTEXT = "candidate_context"
REVIEW_AWARE_CONTEXT = "review_aware_context"
IMPLEMENTATION_CONTEXT = "implementation_context"

# Named inclusion states.
INCL_TRUSTED = "trusted"
INCL_CANDIDATE = "candidate"
INCL_EXCLUDED = "excluded"
INCL_STALE = "stale"
INCL_SUPERSEDED = "superseded"
INCL_NOT_REQUIRED = "not_required"
INCL_DEFERRED = "deferred"

# Bump when the projection build/serialization contract changes — folded into the ids.
PROJECTION_BUILDER_VERSION = "intel-projection-v1"

# --- hard caps --------------------------------------------------------------------------
TITLE_HARD_CAP = 300
SUMMARY_HARD_CAP = 500
EVIDENCE_HARD_CAP = 2_000
OBJECTIVE_HARD_CAP = 500
MAX_ITEMS_HARD_CAP = 500
PACK_CHARS_HARD_CAP = 200_000
ITEM_CHARS_HARD_CAP = 8_000


class ProjectionValidationError(ValueError):
    """Raised on any structural/size/enum problem before a projection row is persisted."""


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def canonical_json(obj: Any) -> str:
    """Deterministic JSON (sorted keys) for scope/policy/budget digests."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"))


# --- budget / policy --------------------------------------------------------------------
@dataclass
class ProjectionBudget:
    max_items: int = 50
    max_chars: int = 60_000
    max_chars_per_item: int = 4_000
    max_trusted: int | None = None
    max_candidates: int | None = None
    include_candidates: bool = True
    include_deferred: bool = False
    include_stale: bool = False
    include_open_loops: bool = True  # advisory only — never executable instructions
    include_evidence: bool = True
    include_metadata: bool = True

    def clamped(self) -> ProjectionBudget:
        return ProjectionBudget(
            max_items=_clamp_int(self.max_items, 1, MAX_ITEMS_HARD_CAP, 50),
            max_chars=_clamp_int(self.max_chars, 1, PACK_CHARS_HARD_CAP, 60_000),
            max_chars_per_item=_clamp_int(self.max_chars_per_item, 1, ITEM_CHARS_HARD_CAP, 4_000),
            max_trusted=(None if self.max_trusted is None
                         else _clamp_int(self.max_trusted, 0, MAX_ITEMS_HARD_CAP, 0)),
            max_candidates=(None if self.max_candidates is None
                            else _clamp_int(self.max_candidates, 0, MAX_ITEMS_HARD_CAP, 0)),
            include_candidates=bool(self.include_candidates),
            include_deferred=bool(self.include_deferred),
            include_stale=bool(self.include_stale),
            include_open_loops=bool(self.include_open_loops),
            include_evidence=bool(self.include_evidence),
            include_metadata=bool(self.include_metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_items": self.max_items, "max_chars": self.max_chars,
            "max_chars_per_item": self.max_chars_per_item, "max_trusted": self.max_trusted,
            "max_candidates": self.max_candidates, "include_candidates": self.include_candidates,
            "include_deferred": self.include_deferred, "include_stale": self.include_stale,
            "include_open_loops": self.include_open_loops, "include_evidence": self.include_evidence,
            "include_metadata": self.include_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ProjectionBudget:
        base = cls()
        if not data:
            return base
        return cls(**{k: data.get(k, getattr(base, k)) for k in base.to_dict()})

    @classmethod
    def for_type(cls, projection_type: str, overrides: dict[str, Any] | None = None) -> ProjectionBudget:
        """Default policy per projection type. ``trusted_context`` excludes candidates by default;
        ``review_aware_context`` includes+labels them; ``implementation_context`` includes trusted +
        candidate context but keeps open loops advisory and excludes stale by default."""
        b = cls()
        if projection_type == TRUSTED_CONTEXT:
            b.include_candidates = False
            b.include_deferred = False
            b.include_stale = False
        elif projection_type in (CANDIDATE_CONTEXT, REVIEW_AWARE_CONTEXT):
            b.include_candidates = True
        elif projection_type == IMPLEMENTATION_CONTEXT:
            b.include_candidates = True
            b.include_stale = False
            b.include_open_loops = True  # advisory only
        merged = {**b.to_dict(), **(overrides or {})}
        return cls.from_dict(merged)


# effective_state → (inclusion_state, is_default_included_when_policy_allows)
# accepted is always trusted+included; rejected/not_required/superseded are always excluded; candidate/
# deferred/stale are policy-gated.
def classify_inclusion_state(effective_state: str | None,
                             budget: ProjectionBudget) -> tuple[str, bool]:
    es = (effective_state or "candidate")
    if es == "accepted":
        return INCL_TRUSTED, True
    if es == "rejected":
        return INCL_EXCLUDED, False
    if es == "not_required":
        return INCL_NOT_REQUIRED, False
    if es == "superseded":
        return INCL_SUPERSEDED, False
    if es == "deferred":
        return INCL_DEFERRED, bool(budget.include_deferred)
    if es == "stale":
        return INCL_STALE, bool(budget.include_stale)
    # candidate / unreviewed / anything else → candidate, policy-gated
    return INCL_CANDIDATE, bool(budget.include_candidates)


# --- deterministic identity -------------------------------------------------------------
def compute_input_digest(item_signals: list[tuple[str, str, str]], filter_policy_json: str,
                         budget_json: str) -> str:
    """Digest over the review-aware inputs: each item's (review_item_id, effective_state, target_digest)
    sorted, plus the policy + budget. A changed disposition (effective_state) changes this digest."""
    joined = ";".join(f"{a}|{b}|{c}" for a, b, c in sorted(item_signals))
    return sha256_hex(f"{joined}#pol={filter_policy_json}#bud={budget_json}")[:24]


def compute_output_digest(included_item_ids: list[str]) -> str:
    return sha256_hex("|".join(sorted(included_item_ids)))[:24]


def compute_projection_id(projection_type: str, scope_json: str, filter_policy_json: str,
                          budget_json: str, input_digest: str) -> str:
    key = (f"{projection_type}|{scope_json}|{filter_policy_json}|{budget_json}|{input_digest}|"
           f"{PROJECTION_BUILDER_VERSION}")
    return sha256_hex(key)[:24]


def compute_projection_item_id(projection_id: str, target_kind: str, target_id: str,
                               review_item_id: str | None, effective_state: str | None,
                               target_digest: str | None) -> str:
    key = (f"{projection_id}|{target_kind}|{target_id}|{review_item_id or ''}|"
           f"{effective_state or ''}|{target_digest or ''}")
    return sha256_hex(key)[:24]


def compute_projection_receipt_id(projection_id: str, input_digest: str, output_digest: str) -> str:
    return sha256_hex(f"{projection_id}|{input_digest}|{output_digest}|{PROJECTION_BUILDER_VERSION}")[:24]


# --- projection item draft --------------------------------------------------------------
_ANCHORS = (
    "source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
    "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id",
    "open_loop_id",
)


def has_provenance(provenance: dict[str, Any]) -> bool:
    return any(provenance.get(a) for a in _ANCHORS)


@dataclass
class ProjectionItem:
    target_kind: str
    target_id: str
    inclusion_state: str
    included: bool
    item_order: int = 0
    review_item_id: str | None = None
    disposition_id: str | None = None
    effective_state: str | None = None
    review_state: str | None = None
    title: str | None = None
    summary: str | None = None
    evidence_excerpt: str | None = None
    confidence: float | None = None
    priority: str | None = None
    token_estimate: int = 0
    exclusion_reason: str | None = None
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
    source_digest: str | None = None
    card_digest: str | None = None
    target_digest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def _provenance(self) -> dict[str, Any]:
        return {a: getattr(self, a) for a in _ANCHORS}

    def to_row(self, projection_id: str) -> dict[str, Any]:
        if self.inclusion_state not in INCLUSION_STATES:
            raise ProjectionValidationError(f"unknown_inclusion_state:{self.inclusion_state}")
        if not self.target_id:
            raise ProjectionValidationError("projection_item_without_target_id")
        if not has_provenance(self._provenance()):
            raise ProjectionValidationError("projection_item_without_provenance")
        row = dict(self._provenance())
        row.update({
            "projection_item_id": compute_projection_item_id(
                projection_id, self.target_kind, self.target_id, self.review_item_id,
                self.effective_state, self.target_digest),
            "projection_id": projection_id,
            "item_order": int(self.item_order),
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "review_item_id": self.review_item_id,
            "disposition_id": self.disposition_id,
            "effective_state": self.effective_state,
            "inclusion_state": self.inclusion_state,
            "review_state": self.review_state,
            "title": bound_text(self.title, TITLE_HARD_CAP) if self.title else None,
            "summary": bound_text(self.summary, SUMMARY_HARD_CAP) if self.summary else None,
            "evidence_excerpt": bound_text(self.evidence_excerpt, EVIDENCE_HARD_CAP)
            if self.evidence_excerpt else None,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "priority": self.priority,
            "token_estimate": max(0, int(self.token_estimate)),
            "included": 1 if self.included else 0,
            "exclusion_reason": self.exclusion_reason,
            "source_digest": self.source_digest,
            "card_digest": self.card_digest,
            "target_digest": self.target_digest,
            "metadata_json": _dump_metadata(self.metadata),
        })
        return row


def _dump_metadata(metadata: dict[str, Any]) -> str | None:
    return json.dumps(metadata, sort_keys=True) if metadata else None
