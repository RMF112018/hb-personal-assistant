"""Retrieval, embeddings and workstream context (Phase 11).

Deterministic + gated semantic search over redacted parser outputs, emails, etc.
WorkstreamContext assembler for briefs/actions.
Pure-python cosine + optional Ollama embeddings. All outputs source-linked + redacted.
"""

from .context import WorkstreamContext, WorkstreamContextBuilder
from .embedder import DeterministicEmbedder, OllamaEmbedder
from .retriever import RetrievalHit, Retriever

__all__ = [
    "Retriever",
    "RetrievalHit",
    "OllamaEmbedder",
    "DeterministicEmbedder",
    "WorkstreamContext",
    "WorkstreamContextBuilder",
]
