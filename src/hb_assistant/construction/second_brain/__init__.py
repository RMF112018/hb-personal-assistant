"""Phase 08A local-first second-brain runtime package.

Prompt 02 lands the read-only contract loader for the V26 second-brain schema. Runtime
builders (retrieval, query tools, chat/memory, daily brief, gates) arrive in later 08A
prompts. No external API access, no writeback, no raw content.
"""

from __future__ import annotations

from .contracts import (
    PHASE_08A_CONTRACT_FILES,
    load_all_phase_08a_contracts,
    load_phase_08a_contract,
)

__all__ = [
    "PHASE_08A_CONTRACT_FILES",
    "load_all_phase_08a_contracts",
    "load_phase_08a_contract",
]
