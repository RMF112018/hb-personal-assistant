"""Phase 08A retrieval policy + Retrieval and Source Broker Agent (A03).

Deterministic, allowlisted retrieval of bounded, redacted, source-linked context.
No raw SQL, no raw source access, no embeddings, no external writeback. The only
path to model-bound context.
"""

from __future__ import annotations

from .broker import (
    RetrievalBroker,
    build_retrieval_broker_agent_proof,
    write_retrieval_receipt,
)
from .models import RetrievalEnvelope, RetrievalItem
from .policy import (
    ALLOWLISTED_SOURCE_FAMILIES,
    EXCLUDED_FAMILIES,
    ContextBudget,
    RetrievalPolicyError,
    apply_context_budget,
    derive_relationship_state,
    load_context_budget,
    load_retrieval_policy_seed,
    relationship_state_tier,
    validate_retrieval_policy,
)

__all__ = [
    "RetrievalBroker",
    "build_retrieval_broker_agent_proof",
    "write_retrieval_receipt",
    "RetrievalEnvelope",
    "RetrievalItem",
    "ALLOWLISTED_SOURCE_FAMILIES",
    "EXCLUDED_FAMILIES",
    "ContextBudget",
    "RetrievalPolicyError",
    "apply_context_budget",
    "derive_relationship_state",
    "load_context_budget",
    "load_retrieval_policy_seed",
    "relationship_state_tier",
    "validate_retrieval_policy",
]
