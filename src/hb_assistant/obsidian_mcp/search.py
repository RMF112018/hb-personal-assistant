"""Semantic/hybrid search with a guaranteed lexical fallback.

The interface accepts ``lexical``, ``semantic``, and ``hybrid`` modes so callers can adopt
semantic search without a future breaking change. Until a local-first vector index is wired
(deferred — no vault content is ever sent to an external embedding service), ``semantic`` and
``hybrid`` degrade to the existing hardened lexical search and report ``mode:
"lexical_fallback"`` with a warning rather than failing.
"""

from __future__ import annotations

from typing import Any

from .config import ObsidianMcpConfig
from .tools import ObsidianMcpToolError, search_vault

_MODES = {"lexical", "semantic", "hybrid"}

# Flipped on only when a local-first vector index is available. Deferred for now;
# until then semantic/hybrid fall back to lexical so the tool never fails.
_SEMANTIC_INDEX_AVAILABLE = False


def semantic_search(
    config: ObsidianMcpConfig,
    *,
    query: str,
    path_scope: str | None = None,
    file_types: list[str] | None = None,
    limit: int = 20,
    mode: str = "hybrid",
    include_snippets: bool = True,
    operator_mode: bool = False,
) -> dict[str, Any]:
    if mode not in _MODES:
        raise ObsidianMcpToolError("unsupported_search_mode")
    lexical = search_vault(
        config,
        query=query,
        path_scope=path_scope,
        file_types=file_types,
        limit=limit,
        include_content_snippet=include_snippets,
        operator_mode=operator_mode,
    )
    if mode == "lexical" or _SEMANTIC_INDEX_AVAILABLE:
        payload: dict[str, Any] = {"query": lexical["query"], "mode": mode, "requested_mode": mode}
    else:
        payload = {
            "query": lexical["query"],
            "mode": "lexical_fallback",
            "requested_mode": mode,
            "warning": "semantic index not configured",
        }
    payload["results"] = lexical["results"]
    return payload
