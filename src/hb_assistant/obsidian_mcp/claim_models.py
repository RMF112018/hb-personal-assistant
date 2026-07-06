"""Neutral claim model + provenance contract (N8C-4).

A claim is an atomic, **source-backed** statement extracted from a source/card/note. This module
holds the shared enums (re-exported from the schema module so the DB CHECKs and the Python layer
never drift), the ingest-input dataclass, and the deterministic claim-id.

Nothing here writes to the DB or runs extraction — see ``claim_repository`` and ``claim_extraction``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_claim_tables import (
    CLAIM_EXTRACTED_BY_VALUES,
    CLAIM_REVIEW_STATE_VALUES,
    CLAIM_STATUS_VALUES,
    CLAIM_TYPE_VALUES,
)

# Re-export enum tuples (single source of truth is the schema module).
CLAIM_TYPES = frozenset(CLAIM_TYPE_VALUES)
CLAIM_STATUSES = frozenset(CLAIM_STATUS_VALUES)
CLAIM_REVIEW_STATES = frozenset(CLAIM_REVIEW_STATE_VALUES)
CLAIM_EXTRACTED_BY = frozenset(CLAIM_EXTRACTED_BY_VALUES)

# Named claim types (avoid magic strings in callers/tests).
FACT = "fact"
DATE = "date"
RISK = "risk"
ASSUMPTION = "assumption"
PREFERENCE = "preference"
COMMITMENT = "commitment"
TASK_CANDIDATE = "task_candidate"
CONTRADICTION_CANDIDATE = "contradiction_candidate"
DECISION_CANDIDATE = "decision_candidate"
UNKNOWN = "unknown"

STATUS_CANDIDATE = "candidate"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
STATUS_SUPERSEDED = "superseded"
STATUS_STALE = "stale"

REVIEW_UNREVIEWED = "unreviewed"

# Source state at extraction time (labels a claim drawn from a stale/deleted source).
SOURCE_STATE_CURRENT = "current"
SOURCE_STATE_STALE = "stale"
SOURCE_STATE_DELETED = "source_deleted"

# Evidence excerpts are bounded so a claim never carries an unbounded blob of source text.
EVIDENCE_MAX_CHARS = 2000


class ClaimValidationError(ValueError):
    """A claim candidate failed provenance / field validation (not written)."""


@dataclass(frozen=True)
class ClaimCandidate:
    """The ingest-input contract for one claim (before it is anchored + written)."""

    claim_type: str
    claim_text: str
    evidence_excerpt: str
    confidence: float = 0.5
    normalized_subject: str | None = None
    normalized_predicate: str | None = None
    normalized_object: str | None = None
    evidence_location: str | None = None
    observed_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    stale_after: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def compute_claim_id(source_id: str | None, note_rel_path: str | None, claim_type: str,
                     claim_text: str) -> str:
    """Deterministic 24-hex id over (source anchor, type, text) so re-extraction is idempotent."""
    key = f"{source_id or ''}|{note_rel_path or ''}|{claim_type}|{claim_text.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def clamp_confidence(value: Any) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, c))


def bound_evidence(text: str) -> str:
    text = (text or "").strip()
    return text[:EVIDENCE_MAX_CHARS]
