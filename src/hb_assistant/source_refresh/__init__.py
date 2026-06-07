"""Unified local source-refresh orchestration.

Composes the existing Procore + Microsoft Graph sync surfaces and the Phase-09
second-brain rebuild/proof surfaces into one safe, dry-run-by-default workflow that
prepares all local data needed before Daily Brief V2 generation.

Guardrails are inherited from the underlying surfaces and re-attested in the
consolidated output: no source-system writeback, no raw bodies/URLs/tokens, no
vectors in SQLite, MCP exposure unchanged. State is local SQLite only.
"""

from __future__ import annotations

from hb_assistant.source_refresh.orchestrator import (
    RefreshOptions,
    SourceRefreshOrchestrator,
)

__all__ = ["RefreshOptions", "SourceRefreshOrchestrator"]
