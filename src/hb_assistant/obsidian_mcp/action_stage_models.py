"""Models, enums, deterministic identity, budget, and bounded caps for the N8C-19 action-staging layer.

Neutral and deterministic (no DB, no vault, no model, NO LLM, no network). Enum tuples are re-exported from
the V110 schema module so DB ``CHECK`` constraints and the Python layer can never drift. A staged item stores
only a bounded ``title`` / ``detail`` (restated from the workflow-section entry it came from) + preserved
provenance ids + copied review/effective state — never a raw source/card/vault/email body, a full workflow/
feedback/packet/draft payload, or a raw prompt/response.

An action stage is a materialized, source-backed READ product built from the N8C-17 workflow CONTEXT envelope
(read-only) + N8C-18 ADVISORY feedback recommendations (read-only). It NEVER executes: every item is pinned to
``execution_status='not_executed'`` / ``external_system='none'`` / ``external_ref=None`` /
``requires_operator_review=1``, and ``staged_state`` is only ``candidate`` or ``blocked``. Determinism makes
rebuilds idempotent; a changed workflow context / feedback recommendation changes ``input_digest`` and yields a
new ``stage_id`` (the prior stage of the same type + workflow + request + policy is superseded by the
repository — a stage-owned row only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_action_stage_tables import (
    ACTION_KIND_VALUES,
    ITEM_STAGE_STATE_VALUES,
    STAGE_EVENT_TYPE_VALUES,
    STAGE_STATUS_VALUES,
    STAGE_TYPE_VALUES,
)

from .memory_models import bound_text, sha256_hex

# Bump when the stage-build / serialization contract changes — folded into every id.
ACTION_STAGE_BUILDER_VERSION = "action-stage-v1"

STAGE_TYPES = frozenset(STAGE_TYPE_VALUES)
STAGE_STATUSES = frozenset(STAGE_STATUS_VALUES)
ACTION_KINDS = frozenset(ACTION_KIND_VALUES)
ITEM_STAGE_STATES = frozenset(ITEM_STAGE_STATE_VALUES)
EVENT_TYPES = frozenset(STAGE_EVENT_TYPE_VALUES)

# Named staged states.
STATE_CANDIDATE = "candidate"
STATE_BLOCKED = "blocked"

# --- fixed policy constants (never overridable; pinned by schema CHECK + asserted by tests) --------------
ACTION_POLICY = "no_execution"
EXECUTION_POLICY = "staged_only"
WORKFLOW_POLICY = "staging_only"
REVIEW_POLICY = "preserve_review_state"
CITATION_POLICY = "preserve_citations"
SOURCE_POLICY = "use_existing_artifacts_only"

STAGE_POLICY_BLOCK = {
    "action_policy": ACTION_POLICY,
    "execution_policy": EXECUTION_POLICY,
    "workflow_policy": WORKFLOW_POLICY,
    "review_policy": REVIEW_POLICY,
    "citation_policy": CITATION_POLICY,
    "source_policy": SOURCE_POLICY,
    "requires_operator_review": 1,
}

# Every staged item is pinned to these non-execution values (mirrored in the schema CHECK).
ITEM_EXECUTION_STATUS = "not_executed"
ITEM_EXTERNAL_SYSTEM = "none"

# --- hard caps --------------------------------------------------------------------------
TITLE_HARD_CAP = 300
DETAIL_HARD_CAP = 2_000
BLOCK_REASON_HARD_CAP = 200
LABEL_HARD_CAP = 200
ID_HARD_CAP = 200
REF_HARD_CAP = 500
MAX_ITEMS_HARD_CAP = 500
MAX_ITEMS_PER_SECTION_HARD_CAP = 100
MAX_CITATIONS_PER_ITEM_HARD_CAP = 25
STAGE_CHARS_HARD_CAP = 200_000

# Typed upstream anchors a staged item / citation may carry (bounded ids only — never a body).
ITEM_ANCHOR_FIELDS: tuple[str, ...] = (
    "workflow_id", "draft_id", "packet_id", "projection_item_id", "context_pack_id", "memory_node_id",
    "decision_id", "preference_id", "open_loop_id", "review_item_id", "claim_id", "citation_id",
    "feedback_id", "recommendation_id", "source_id", "source_ref", "source_root_key", "rel_path",
    "note_rel_path",
)
# A citation must carry at least one of these (mirrors the schema provenance CHECK; target_id also satisfies).
CITATION_ANCHOR_FIELDS: tuple[str, ...] = (*ITEM_ANCHOR_FIELDS,)


class ActionStageValidationError(ValueError):
    """Raised on a structural/enum/size problem building a stage / item / citation row."""


def canonical_json(obj: Any) -> str:
    """Deterministic JSON (sorted keys) for policy/budget/context digests folded into stage ids."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"), default=str)


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def _clean_id(value: Any, cap: int = ID_HARD_CAP) -> str | None:
    if value is None:
        return None
    text = bound_text(str(value).strip(), cap)
    return text or None


# --- budget / policy --------------------------------------------------------------------
@dataclass
class ActionStageBudget:
    max_items: int = 50
    max_items_per_section: int = 15
    max_chars: int = 60_000
    max_citations_per_item: int = 6
    include_candidates: bool = True
    include_blocked: bool = True
    include_source_refs: bool = True
    include_citation_excerpts: bool = False

    def clamped(self) -> ActionStageBudget:
        return ActionStageBudget(
            max_items=_clamp_int(self.max_items, 1, MAX_ITEMS_HARD_CAP, 50),
            max_items_per_section=_clamp_int(self.max_items_per_section, 1,
                                             MAX_ITEMS_PER_SECTION_HARD_CAP, 15),
            max_chars=_clamp_int(self.max_chars, 1, STAGE_CHARS_HARD_CAP, 60_000),
            max_citations_per_item=_clamp_int(self.max_citations_per_item, 0,
                                              MAX_CITATIONS_PER_ITEM_HARD_CAP, 6),
            include_candidates=bool(self.include_candidates),
            include_blocked=bool(self.include_blocked),
            include_source_refs=bool(self.include_source_refs),
            include_citation_excerpts=False,  # never carry excerpts — bounded ids/metadata only
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_items": self.max_items, "max_items_per_section": self.max_items_per_section,
            "max_chars": self.max_chars, "max_citations_per_item": self.max_citations_per_item,
            "include_candidates": self.include_candidates, "include_blocked": self.include_blocked,
            "include_source_refs": self.include_source_refs,
            "include_citation_excerpts": self.include_citation_excerpts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ActionStageBudget:
        base = cls()
        if not data:
            return base
        return cls(**{k: data.get(k, getattr(base, k)) for k in base.to_dict()})


# --- payload dataclasses ----------------------------------------------------------------
@dataclass
class ActionStageItem:
    """One proposed follow-up CANDIDATE. ``candidate`` = surfaced for operator review; ``blocked`` = withheld
    (e.g. an execution-like advisory step or a terminal source) with a bounded ``block_reason``."""

    action_kind: str
    staged_state: str = STATE_CANDIDATE
    source_section: str | None = None
    title: str | None = None
    detail: str | None = None
    block_reason: str | None = None
    target_kind: str | None = None
    target_id: str | None = None
    anchors: dict[str, Any] = field(default_factory=dict)
    review_state: str | None = None
    effective_state: str | None = None
    item_digest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_anchors(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name in ITEM_ANCHOR_FIELDS:
            val = _clean_id(self.anchors.get(name), REF_HARD_CAP)
            if val:
                out[name] = val
        return out

    def signature(self) -> str:
        anchors = ";".join(f"{k}={v}" for k, v in sorted(self.normalized_anchors().items()))
        return f"{self.action_kind}|{self.staged_state}|{self.target_kind or ''}|{self.target_id or ''}|{anchors}"

    def to_row(self, stage_id: str, order: int) -> dict[str, Any]:
        if self.action_kind not in ACTION_KINDS:
            raise ActionStageValidationError(f"unknown_action_kind:{self.action_kind}")
        if self.staged_state not in ITEM_STAGE_STATES:
            raise ActionStageValidationError(f"unknown_staged_state:{self.staged_state}")
        row: dict[str, Any] = {
            "stage_item_id": compute_stage_item_id(stage_id, self.action_kind, self.target_kind,
                                                   self.target_id, order),
            "stage_id": stage_id,
            "item_order": int(order),
            "action_kind": self.action_kind,
            "staged_state": self.staged_state,
            "source_section": _clean_id(self.source_section, LABEL_HARD_CAP),
            "title": bound_text(self.title, TITLE_HARD_CAP) or None,
            "detail": bound_text(self.detail, DETAIL_HARD_CAP) or None,
            "block_reason": bound_text(self.block_reason, BLOCK_REASON_HARD_CAP) or None,
            # Pinned non-execution values (defense-in-depth alongside the schema CHECK).
            "execution_status": ITEM_EXECUTION_STATUS,
            "external_system": ITEM_EXTERNAL_SYSTEM,
            "external_ref": None,
            "requires_operator_review": 1,
            "target_kind": self.target_kind or None,
            "target_id": _clean_id(self.target_id),
            "review_state": self.review_state or None,
            "effective_state": self.effective_state or None,
            "item_digest": _clean_id(self.item_digest, REF_HARD_CAP),
            "metadata_json": canonical_json(self.metadata) if self.metadata else None,
        }
        row.update(self.normalized_anchors())
        return row


@dataclass
class ActionStageCitation:
    """A bounded provenance bridge from a staged item to the existing artifact(s) it is grounded in."""

    stage_item_id: str
    citation_order: int = 0
    citation_type: str | None = None
    target_kind: str | None = None
    target_id: str | None = None
    citation_label: str | None = None
    anchors: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_anchors(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name in CITATION_ANCHOR_FIELDS:
            val = _clean_id(self.anchors.get(name), REF_HARD_CAP)
            if val:
                out[name] = val
        return out

    def to_row(self, stage_id: str, order: int) -> dict[str, Any]:
        anchors = self.normalized_anchors()
        tid = _clean_id(self.target_id)
        if not tid and not anchors:
            raise ActionStageValidationError("citation_without_provenance_anchor")
        row: dict[str, Any] = {
            "stage_citation_id": compute_stage_citation_id(stage_id, self.stage_item_id,
                                                           self.citation_type, tid, order),
            "stage_id": stage_id,
            "stage_item_id": self.stage_item_id,
            "citation_order": int(order),
            "citation_type": _clean_id(self.citation_type, LABEL_HARD_CAP),
            "target_kind": self.target_kind or None,
            "target_id": tid,
            "citation_label": bound_text(self.citation_label, LABEL_HARD_CAP) or None,
            "metadata_json": canonical_json(self.metadata) if self.metadata else None,
        }
        row.update(anchors)
        return row


# --- deterministic identity -------------------------------------------------------------
def compute_request_digest(stage_type: str, workflow_type: str | None, workflow_id: str | None,
                           stage_policy_json: str, budget_json: str) -> str:
    """Lineage key: identical (stage_type, workflow, policy, budget) → same request_digest → supersede
    lineage (a rebuild with changed context supersedes the prior stage of this lineage)."""
    return sha256_hex(
        f"{stage_type}|{workflow_type or ''}|{workflow_id or ''}|{stage_policy_json}|{budget_json}")[:24]


def compute_source_context_digest(item_signatures: list[str]) -> str:
    """Digest over the ordered staged-item signatures — the workflow-context/feedback inputs the stage was
    built from. A changed context (item added/removed/relabeled) changes this digest."""
    return sha256_hex("|".join(sorted(item_signatures)))[:24]


def compute_stage_input_digest(request_digest: str, source_context_digest: str) -> str:
    return sha256_hex(f"{request_digest}#{source_context_digest}#{ACTION_STAGE_BUILDER_VERSION}")[:24]


def compute_stage_output_digest(item_ids: list[str]) -> str:
    return sha256_hex("|".join(sorted(item_ids)))[:24]


def compute_stage_id(stage_type: str, workflow_type: str | None, request_digest: str,
                     input_digest: str) -> str:
    key = f"{stage_type}|{workflow_type or ''}|{request_digest}|{input_digest}|{ACTION_STAGE_BUILDER_VERSION}"
    return sha256_hex(key)[:24]


def compute_stage_item_id(stage_id: str, action_kind: str, target_kind: str | None,
                          target_id: str | None, order: int) -> str:
    return sha256_hex(
        f"{stage_id}|{action_kind}|{target_kind or ''}|{target_id or ''}|{int(order)}")[:24]


def compute_stage_citation_id(stage_id: str, stage_item_id: str, citation_type: str | None,
                              target_id: str | None, order: int) -> str:
    return sha256_hex(
        f"{stage_id}|{stage_item_id}|{citation_type or ''}|{target_id or ''}|{int(order)}")[:24]


def compute_stage_receipt_id(stage_id: str, input_digest: str, output_digest: str) -> str:
    return sha256_hex(
        f"{stage_id}|{input_digest}|{output_digest}|{ACTION_STAGE_BUILDER_VERSION}")[:24]
