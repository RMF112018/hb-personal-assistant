"""Phase 08A allowlisted read-only SQLite query tools (Prompt 06).

Named, allowlisted query-tool service functions over approved local read-models.
No arbitrary / model-generated SQL, read-only transaction posture, bounded results,
mandatory source refs + review tiers, metadata-only receipts. Sits below the
retrieval orchestrator (Prompt 07); tools provide facts, never final answers.
"""

from __future__ import annotations

from .models import QueryToolReceipt, QueryToolResult
from .policy import (
    ALLOWLISTED_QUERY_TOOLS,
    QUERY_TOOL_FAMILY_MAP,
    QueryToolError,
    load_query_tool_allowlist_seed,
    validate_query_tool_policy,
)
from .store import read_latest_query_tool_receipts, write_query_tool_receipt
from .tools import (
    build_sqlite_query_tool_proof,
    list_query_tools,
    read_only_connection,
    run_query_tool,
)

__all__ = [
    "QueryToolReceipt",
    "QueryToolResult",
    "ALLOWLISTED_QUERY_TOOLS",
    "QUERY_TOOL_FAMILY_MAP",
    "QueryToolError",
    "load_query_tool_allowlist_seed",
    "validate_query_tool_policy",
    "read_latest_query_tool_receipts",
    "write_query_tool_receipt",
    "build_sqlite_query_tool_proof",
    "list_query_tools",
    "read_only_connection",
    "run_query_tool",
]
