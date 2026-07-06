"""Models, enums, budget, and pure helpers for the N8C-6 context-pack layer.

Neutral and deterministic: the enum tuples are re-exported from the V102 schema module
(:mod:`hb_assistant.store.assistant_context_pack_tables`) so the DB ``CHECK`` constraints and the
Python layer can never drift. Text columns are hard-capped here before the repository writes them —
a pack item stores only a **bounded selected excerpt**, never a full enrichment ``result_json`` (the
source enrichment output is linked by ``receipt_id`` + ``result_digest``).

Nothing here reads a DB, the vault, or a model. ``compute_pack_id`` makes a pack reproducible and
idempotent: identical inputs → identical ``pack_id``; a changed ``input_digest`` → a new ``pack_id``.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_context_pack_tables import (
    CONTEXT_PACK_EVENT_TYPE_VALUES,
    CONTEXT_PACK_ITEM_TYPE_VALUES,
    CONTEXT_PACK_REVIEW_TIER_VALUES,
    CONTEXT_PACK_STATUS_VALUES,
    CONTEXT_PACK_TYPE_VALUES,
)

# --- enum re-exports (single source of truth = the schema module) -----------------------
PACK_TYPES = frozenset(CONTEXT_PACK_TYPE_VALUES)
PACK_STATUSES = frozenset(CONTEXT_PACK_STATUS_VALUES)
ITEM_TYPES = frozenset(CONTEXT_PACK_ITEM_TYPE_VALUES)
REVIEW_TIERS = frozenset(CONTEXT_PACK_REVIEW_TIER_VALUES)
EVENT_TYPES = frozenset(CONTEXT_PACK_EVENT_TYPE_VALUES)

# Named pack types.
PACK_ENRICHMENT_REVIEW = "enrichment_review"
PACK_SOURCE_REVIEW = "source_review"
PACK_IMPLEMENTATION_CONTEXT = "implementation_context"

# Named statuses.
STATUS_DRAFT = "draft"
STATUS_BUILT = "built"
STATUS_STALE = "stale"
STATUS_SUPERSEDED = "superseded"
STATUS_FAILED = "failed"

# Named item types.
ITEM_SOURCE_SUMMARY = "source_summary"
ITEM_CLAIM_CANDIDATE = "claim_candidate"
ITEM_BACKLINK_SUGGESTION = "backlink_suggestion"
ITEM_SOURCE = "source"
ITEM_UNKNOWN = "unknown"

# Named review tiers (advisory; distinct from a claim's review_state — nothing here accepts a claim).
TIER_SAFE_SUMMARY = "safe_summary"
TIER_NEEDS_OPERATOR_REVIEW = "needs_operator_review"
TIER_SOURCE_STALE = "source_stale"
TIER_CLAIM_CANDIDATE = "claim_candidate"
TIER_LINK_CANDIDATE = "link_candidate"
TIER_LOW_CONFIDENCE = "low_confidence"
TIER_CONFLICT_OR_CONTRADICTION = "conflict_or_contradiction"

# Named lifecycle events.
EVENT_CREATED = "created"
EVENT_BUILT = "built"
EVENT_MARKED_STALE = "marked_stale"
EVENT_SUPERSEDED = "superseded"

# How much per-item content to include.
CONTENT_METADATA_ONLY = "metadata_only"
CONTENT_EXCERPT = "excerpt"
CONTENT_DEEP_BOUNDED = "deep_bounded"
CONTENT_LEVELS = frozenset({CONTENT_METADATA_ONLY, CONTENT_EXCERPT, CONTENT_DEEP_BOUNDED})

# Bump when the assembly/serialization contract changes — folded into pack_id so a builder change
# yields a distinct reproducible pack.
BUILDER_VERSION = "context-pack-v1"

# --- hard ceilings (enforced regardless of a requested budget) --------------------------
ITEM_EXCERPT_HARD_CAP = 8_000       # a single item's content_excerpt can never exceed this
EVIDENCE_HARD_CAP = 2_000           # a single item's evidence_excerpt ceiling
TITLE_HARD_CAP = 300
PACK_CHARS_HARD_CAP = 200_000       # total assembled excerpt chars ceiling
MAX_ITEMS_HARD_CAP = 500

# Conservative char→token estimate. No tokenizer exists in the N8C lineage; 4 chars/token is the
# standard conservative rule of thumb and is documented so callers know it is an ESTIMATE.
CHARS_PER_TOKEN = 4

_TRUNC_MARK = "…[truncated]"


class ContextPackValidationError(ValueError):
    """Raised on any structural/size/enum problem before a pack or item is persisted."""


@dataclass(frozen=True)
class Budget:
    """Deterministic bounds for pack assembly. Requested values are clamped to the hard ceilings."""

    max_items: int = 50
    max_chars: int = 60_000
    max_chars_per_item: int = 4_000
    max_claims: int = 100
    max_sources: int = 50
    max_receipts: int = 100
    include_content_level: str = CONTENT_DEEP_BOUNDED

    def normalized(self) -> Budget:
        level = self.include_content_level if self.include_content_level in CONTENT_LEVELS \
            else CONTENT_DEEP_BOUNDED
        return Budget(
            max_items=_clamp_int(self.max_items, 1, MAX_ITEMS_HARD_CAP, 50),
            max_chars=_clamp_int(self.max_chars, 1, PACK_CHARS_HARD_CAP, 60_000),
            max_chars_per_item=_clamp_int(self.max_chars_per_item, 1, ITEM_EXCERPT_HARD_CAP, 4_000),
            max_claims=_clamp_int(self.max_claims, 0, 10_000, 100),
            max_sources=_clamp_int(self.max_sources, 0, 10_000, 50),
            max_receipts=_clamp_int(self.max_receipts, 0, 10_000, 100),
            include_content_level=level,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_items": self.max_items,
            "max_chars": self.max_chars,
            "max_chars_per_item": self.max_chars_per_item,
            "max_claims": self.max_claims,
            "max_sources": self.max_sources,
            "max_receipts": self.max_receipts,
            "include_content_level": self.include_content_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Budget:
        data = data or {}
        base = cls()
        return cls(
            max_items=int(data.get("max_items", base.max_items)),
            max_chars=int(data.get("max_chars", base.max_chars)),
            max_chars_per_item=int(data.get("max_chars_per_item", base.max_chars_per_item)),
            max_claims=int(data.get("max_claims", base.max_claims)),
            max_sources=int(data.get("max_sources", base.max_sources)),
            max_receipts=int(data.get("max_receipts", base.max_receipts)),
            include_content_level=str(data.get("include_content_level", base.include_content_level)),
        ).normalized()


@dataclass
class PackItem:
    """One assembled provenance item. ``included`` False items carry an ``exclusion_reason`` and no
    excerpt (budget/stale trims are recorded, never silently dropped)."""

    item_type: str
    item_order: int = 0
    source_id: str | None = None
    note_rel_path: str | None = None
    claim_id: str | None = None
    job_id: str | None = None
    receipt_id: str | None = None
    title: str | None = None
    content_excerpt: str | None = None
    evidence_excerpt: str | None = None
    source_digest: str | None = None
    card_digest: str | None = None
    result_digest: str | None = None
    source_state: str | None = None
    confidence: float | None = None
    review_tier: str | None = None
    token_estimate: int = 0
    included: bool = True
    exclusion_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_row(self, pack_id: str) -> dict[str, Any]:
        return {
            "pack_id": pack_id,
            "item_order": int(self.item_order),
            "item_type": self.item_type,
            "source_id": self.source_id,
            "note_rel_path": self.note_rel_path,
            "claim_id": self.claim_id,
            "job_id": self.job_id,
            "receipt_id": self.receipt_id,
            "title": bound_text(self.title, TITLE_HARD_CAP) if self.title else None,
            "content_excerpt": self.content_excerpt,
            "evidence_excerpt": self.evidence_excerpt,
            "source_digest": self.source_digest,
            "card_digest": self.card_digest,
            "result_digest": self.result_digest,
            "source_state": self.source_state,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "review_tier": self.review_tier,
            "token_estimate": max(0, int(self.token_estimate)),
            "included": 1 if self.included else 0,
            "exclusion_reason": self.exclusion_reason,
            "metadata_json": json.dumps(self.metadata, sort_keys=True) if self.metadata else None,
        }


# --- pure helpers -----------------------------------------------------------------------
def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def clamp_confidence(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def estimate_tokens(text: str | None) -> int:
    """Conservative char-based token ESTIMATE (``CHARS_PER_TOKEN`` chars/token). Not a real tokenizer."""
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def bound_text(text: Any, cap: int) -> str:
    """Truncate a selected excerpt to ``cap`` chars, appending a visible marker when trimmed."""
    s = "" if text is None else str(text)
    if len(s) <= cap:
        return s
    return s[: max(0, cap - len(_TRUNC_MARK))] + _TRUNC_MARK


def normalize_scope(scope: dict[str, Any] | None) -> str:
    """Deterministic canonical JSON for the pack scope (feeds ``pack_id`` + reproducibility)."""
    return json.dumps(_canonical(scope or {}), sort_keys=True, separators=(",", ":"))


def normalize_budget(budget: Budget | dict[str, Any] | None) -> str:
    """Deterministic canonical JSON for the (normalized) budget."""
    if isinstance(budget, Budget):
        data = budget.normalized().to_dict()
    else:
        data = Budget.from_dict(budget).to_dict()
    return json.dumps(_canonical(data), sort_keys=True, separators=(",", ":"))


def _canonical(obj: Any) -> Any:
    """Sort lists of scalars so scope ordering never changes the digest; recurse into dict/list."""
    if isinstance(obj, dict):
        return {k: _canonical(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        converted = [_canonical(x) for x in obj]
        if all(isinstance(x, (str, int, float, bool)) for x in converted):
            return sorted(converted, key=lambda x: (type(x).__name__, str(x)))
        return converted
    return obj


def compute_pack_id(
    pack_type: str,
    *,
    scope_json: str,
    budget_json: str,
    input_digest: str,
    builder_version: str = BUILDER_VERSION,
) -> str:
    """Deterministic 24-hex id. Same (type, scope, budget, input_digest, builder_version) → same
    ``pack_id``; a changed ``input_digest`` → a new ``pack_id``. The builder never silently
    overwrites an existing pack with the same id."""
    key = f"{pack_type}|{scope_json}|{budget_json}|{input_digest}|{builder_version}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def validate_pack_type(pack_type: str) -> str:
    if pack_type not in PACK_TYPES:
        raise ContextPackValidationError(f"unknown_pack_type:{pack_type}")
    return pack_type


def validate_status(status: str) -> str:
    if status not in PACK_STATUSES:
        raise ContextPackValidationError(f"unknown_pack_status:{status}")
    return status
