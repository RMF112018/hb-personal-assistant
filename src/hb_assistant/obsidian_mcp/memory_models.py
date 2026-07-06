"""Models, enums, deterministic identity, and normalization for the N8C-7 memory compiler.

Neutral and deterministic (no DB, no vault, no model). Enum tuples are re-exported from the V103
schema module so the DB ``CHECK`` constraints and the Python layer can never drift. Text columns are
hard-capped here before the repository writes them — a memory record stores only bounded excerpts,
never a raw source/email body or a raw prompt/response.

Identity is deterministic so re-running the compiler is idempotent: a node keyed by its normalized
identity keeps the same ``node_id``; a mention by its anchor keeps the same ``mention_id``; a
compilation by its input state keeps the same ``compilation_id`` (a changed input digest → a new one).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_memory_tables import (
    MEMORY_COMPILATION_STATUS_VALUES,
    MEMORY_COMPILE_TYPE_VALUES,
    MEMORY_EVENT_TYPE_VALUES,
    MEMORY_MENTION_TYPE_VALUES,
    MEMORY_NODE_STATUS_VALUES,
    MEMORY_NODE_TYPE_VALUES,
    MEMORY_REVIEW_TIER_VALUES,
)

# --- enum re-exports (single source of truth = the schema module) -----------------------
NODE_TYPES = frozenset(MEMORY_NODE_TYPE_VALUES)
NODE_STATUSES = frozenset(MEMORY_NODE_STATUS_VALUES)
MENTION_TYPES = frozenset(MEMORY_MENTION_TYPE_VALUES)
REVIEW_TIERS = frozenset(MEMORY_REVIEW_TIER_VALUES)
COMPILE_TYPES = frozenset(MEMORY_COMPILE_TYPE_VALUES)
COMPILATION_STATUSES = frozenset(MEMORY_COMPILATION_STATUS_VALUES)
EVENT_TYPES = frozenset(MEMORY_EVENT_TYPE_VALUES)

# Named node types.
NODE_ENTITY = "entity"
NODE_CONCEPT = "concept"
NODE_DOMAIN = "domain"
NODE_PROJECT = "project"
NODE_PERSON = "person"
NODE_ORGANIZATION = "organization"
NODE_TOPIC = "topic"
NODE_UNKNOWN = "unknown"

# Named node statuses (N8C-7 uses active/stale/superseded; merged/archived reserved for a future slice).
STATUS_ACTIVE = "active"
STATUS_STALE = "stale"
STATUS_SUPERSEDED = "superseded"

# Named mention types.
MENTION_CLAIM_SUBJECT = "claim_subject"
MENTION_CLAIM_OBJECT = "claim_object"
MENTION_SOURCE_TITLE = "source_title"
MENTION_CONTEXT_PACK_ITEM = "context_pack_item"
MENTION_ENRICHMENT_SUMMARY = "enrichment_summary"
MENTION_BACKLINK_TARGET = "backlink_target"
MENTION_MANUAL_SEED = "manual_seed"
MENTION_UNKNOWN = "unknown"

# Named review tiers (advisory provenance quality — NEVER a claim disposition).
TIER_TRUSTED_SOURCE_BACKED = "trusted_source_backed"
TIER_NEEDS_OPERATOR_REVIEW = "needs_operator_review"
TIER_LOW_CONFIDENCE = "low_confidence"
TIER_STALE_SOURCE = "stale_source"
TIER_AMBIGUOUS_SOURCE = "ambiguous_source"
TIER_CANDIDATE_ONLY = "candidate_only"
TIER_CONFLICT_POSSIBLE = "conflict_possible"

# Cautious-first ordering: a node's tier is the WORST (lowest-rank) of its mentions.
_TIER_RANK = {
    TIER_AMBIGUOUS_SOURCE: 0,
    TIER_NEEDS_OPERATOR_REVIEW: 1,
    TIER_STALE_SOURCE: 2,
    TIER_CONFLICT_POSSIBLE: 3,
    TIER_LOW_CONFIDENCE: 4,
    TIER_CANDIDATE_ONLY: 5,
    TIER_TRUSTED_SOURCE_BACKED: 6,
}

# Named compile types.
COMPILE_NODE_SUMMARY = "node_summary"
COMPILE_DOMAIN_SUMMARY = "domain_summary"
COMPILE_PROJECT_SUMMARY = "project_summary"
COMPILE_TOPIC_SUMMARY = "topic_summary"

# Bump when the compile/serialization contract changes — folded into compilation_id.
COMPILER_VERSION = "memory-compiler-v1"

# --- hard caps --------------------------------------------------------------------------
NAME_HARD_CAP = 300
MENTION_TEXT_CAP = 500
EVIDENCE_HARD_CAP = 2_000
SUMMARY_HARD_CAP = 8_000
KEY_POINTS_MAX = 20
KEY_POINT_CAP = 500
ALIASES_MAX = 50
LOW_CONFIDENCE_THRESHOLD = 0.4

CHARS_PER_TOKEN = 4
_TRUNC_MARK = "…[truncated]"
_WS = re.compile(r"\s+")
_PUNCT_EDGE = re.compile(r"^[\s\"'`.,;:!?()\[\]{}<>|/\\-]+|[\s\"'`.,;:!?()\[\]{}<>|/\\-]+$")


class MemoryValidationError(ValueError):
    """Raised on any structural/size/enum problem before a memory record is persisted."""


# --- pure helpers -----------------------------------------------------------------------
def clamp_confidence(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def bound_text(text: Any, cap: int) -> str:
    s = "" if text is None else str(text)
    if len(s) <= cap:
        return s
    return s[: max(0, cap - len(_TRUNC_MARK))] + _TRUNC_MARK


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return -(-len(text) // CHARS_PER_TOKEN)  # ceil


def normalize_memory_name(name: str | None) -> str:
    """Conservative normalization for the identity key: lowercase, trim, collapse whitespace, strip
    edge punctuation. NOT fuzzy — exact/normalized matching only. The canonical display name is kept
    separately by the caller."""
    s = (name or "").strip().lower()
    s = _WS.sub(" ", s)
    s = _PUNCT_EDGE.sub("", s)
    return _WS.sub(" ", s).strip()


def worst_tier(tiers: list[str]) -> str:
    """The most-cautious tier among a set (a node inherits its worst mention's tier)."""
    ranked = [t for t in tiers if t in _TIER_RANK]
    if not ranked:
        return TIER_NEEDS_OPERATOR_REVIEW
    return min(ranked, key=lambda t: _TIER_RANK[t])


def compute_node_id(node_type: str, normalized_name: str, domain: str | None) -> str:
    key = f"{node_type}|{normalized_name}|{domain or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def compute_mention_id(node_id: str, *, source_id: str | None, claim_id: str | None,
                       pack_item_id: str | None, mention_text: str | None,
                       mention_type: str) -> str:
    key = f"{node_id}|{source_id or ''}|{claim_id or ''}|{pack_item_id or ''}|" \
          f"{mention_type}|{mention_text or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def compute_compilation_id(node_id: str, compile_type: str, input_digest: str,
                           compiler_version: str = COMPILER_VERSION) -> str:
    key = f"{node_id}|{compile_type}|{input_digest}|{compiler_version}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


@dataclass
class MemoryMention:
    """One source-backed piece of evidence that a node appears somewhere."""

    mention_type: str
    mention_text: str | None = None
    source_id: str | None = None
    note_rel_path: str | None = None
    claim_id: str | None = None
    job_id: str | None = None
    receipt_id: str | None = None
    pack_id: str | None = None
    pack_item_id: str | None = None
    evidence_excerpt: str | None = None
    source_digest: str | None = None
    card_digest: str | None = None
    confidence: float | None = None
    review_tier: str | None = None
    source_state: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_provenance(self) -> bool:
        return any((self.source_id, self.note_rel_path, self.claim_id, self.receipt_id,
                    self.pack_id, self.pack_item_id))

    def to_row(self, node_id: str) -> dict[str, Any]:
        if self.mention_type not in MENTION_TYPES:
            raise MemoryValidationError(f"unknown_mention_type:{self.mention_type}")
        if not self.has_provenance():
            raise MemoryValidationError("mention_without_provenance")
        return {
            "mention_id": compute_mention_id(
                node_id, source_id=self.source_id, claim_id=self.claim_id,
                pack_item_id=self.pack_item_id, mention_text=self.mention_text,
                mention_type=self.mention_type),
            "node_id": node_id,
            "mention_type": self.mention_type,
            "mention_text": bound_text(self.mention_text, MENTION_TEXT_CAP) if self.mention_text else None,
            "source_id": self.source_id,
            "note_rel_path": self.note_rel_path,
            "claim_id": self.claim_id,
            "job_id": self.job_id,
            "receipt_id": self.receipt_id,
            "pack_id": self.pack_id,
            "pack_item_id": self.pack_item_id,
            "evidence_excerpt": bound_text(self.evidence_excerpt, EVIDENCE_HARD_CAP) if self.evidence_excerpt else None,
            "source_digest": self.source_digest,
            "card_digest": self.card_digest,
            "confidence": clamp_confidence(self.confidence) if self.confidence is not None else None,
            "review_tier": self.review_tier,
            "source_state": self.source_state,
            "metadata_json": json.dumps(self.metadata, sort_keys=True) if self.metadata else None,
        }


@dataclass
class MemoryNodeDraft:
    """A candidate node plus its mentions, before persistence."""

    node_type: str
    canonical_name: str
    domain: str | None = None
    mentions: list[MemoryMention] = field(default_factory=list)

    @property
    def normalized_name(self) -> str:
        return normalize_memory_name(self.canonical_name)

    @property
    def node_id(self) -> str:
        return compute_node_id(self.node_type, self.normalized_name, self.domain)


def validate_node_type(node_type: str) -> str:
    if node_type not in NODE_TYPES:
        raise MemoryValidationError(f"unknown_node_type:{node_type}")
    return node_type


def validate_compile_type(compile_type: str) -> str:
    if compile_type not in COMPILE_TYPES:
        raise MemoryValidationError(f"unknown_compile_type:{compile_type}")
    return compile_type
