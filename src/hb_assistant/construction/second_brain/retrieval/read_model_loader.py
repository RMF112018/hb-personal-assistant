"""Phase 09 — approved deterministic read-model → safe vector-node loader.

Bridges the deterministic, allowlisted read-model families (served by ``READER_REGISTRY``) into the
semantic-retrieval plane. The dedicated Obsidian / reviewed-memory / generated-outputs loaders already
cover their families; this loader covers the *other* embeddable read-model families
(evidence trails, issue history, risk digest, aging exposure, cross-source relationships, and — per
the embedding policy seed — meeting-prep sections and review-controlled correspondence context).

It admits only **eligible** items — redacted excerpt present, source-linked (non-empty ``source_ref``
+ allowlisted family), **not review-required**, and ``review_tier <= 2`` — so no high-impact /
review-required item is ever vector-indexed (review-control guardrail preserved). Each eligible item
becomes a metadata-only vector node carrying only the bounded ``content_excerpt_redacted`` text
(``text_redacted``) plus hashes/labels: no raw bodies, prompts, responses, URLs, tokens, or secrets,
and no vectors. This module is read-only and is the single shared source for both the approved-source
manifest's ``approved_read_models`` category and the vector-index node gather.
"""

from __future__ import annotations

import hashlib
from typing import Any

from hb_assistant.construction.store import ConstructionStore

from .embedding_policy import embeddable_families, load_embedding_vector_policy_seed
from .models import RetrievalItem
from .policy import EXCLUDED_FAMILIES
from .readers import READER_REGISTRY

# Families already brought into the vector index by their own dedicated node loaders.
_DEDICATED_LOADER_FAMILIES: frozenset[str] = frozenset(
    {
        "approved_obsidian_generated_outputs",
        "accepted_long_term_memory",
        "generated_outputs",
    }
)

_EXCERPT_MAX_CHARS = 280


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_model_loader_families(seed: dict[str, Any] | None = None) -> list[str]:
    """Embeddable read-model families served here: embeddable ∩ readers − dedicated-loader families."""
    seed = seed or load_embedding_vector_policy_seed()
    return [
        f
        for f in embeddable_families(seed)
        if f in READER_REGISTRY and f not in _DEDICATED_LOADER_FAMILIES
    ]


def _eligible(item: RetrievalItem) -> bool:
    """An item may be admitted iff redacted + source-linked + not review-required + tier <= 2."""
    return (
        bool(item.content_excerpt_redacted)
        and bool(item.source_ref)
        and item.source_family not in EXCLUDED_FAMILIES
        and item.review_required is False
        and item.review_tier <= 2
    )


def iter_approved_read_model_items(
    db_path: str | None, project_key: str | None = None
) -> list[RetrievalItem]:
    """Run each served family's deterministic reader and keep only the eligible items (read-only)."""
    store = ConstructionStore(db_path)
    seed = load_embedding_vector_policy_seed()
    items: list[RetrievalItem] = []
    for family in read_model_loader_families(seed):
        reader = READER_REGISTRY.get(family)
        if reader is None:
            continue
        for item in reader(store, db_path, project_key):
            if _eligible(item):
                items.append(item)
    return items


def load_approved_read_model_nodes(
    db_path: str | None, *, project_key: str | None = None
) -> list[dict[str, Any]]:
    """Convert eligible deterministic read-model items into metadata-only vector nodes.

    Returned node dicts mirror the other loaders' shape (``node_id`` / ``source_family`` /
    ``source_ref`` / ``content_hash`` / ``confidence_class`` / ``review_tier`` / ``review_status`` /
    ``review_required`` / ``freshness_label`` / ``text_redacted``). Only the bounded redacted excerpt
    is carried as text; never persisted by this module.
    """
    nodes: list[dict[str, Any]] = []
    for item in iter_approved_read_model_items(db_path, project_key):
        excerpt = item.content_excerpt_redacted[:_EXCERPT_MAX_CHARS]
        source_ref = item.source_ref
        nodes.append(
            {
                "node_id": _hash(f"{item.source_family}:{source_ref}")[:48],
                "source_family": item.source_family,
                "source_ref": source_ref,
                "content_hash": _hash(f"{item.source_family}:{source_ref}:{excerpt}")[:64],
                "confidence_class": item.confidence_class or "unknown",
                "review_tier": item.review_tier,
                "review_status": item.review_status,
                "review_required": item.review_required,
                "freshness_label": "current" if item.recency else "unknown",
                "text_redacted": excerpt,
            }
        )
    return nodes
