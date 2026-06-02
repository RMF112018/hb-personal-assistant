"""Phase 08A local-first second-brain runtime package.

Prompt 02 landed the read-only contract loader for the V26 second-brain schema.
Prompt 03 adds the runtime config surface and the mock/live Claude adapter
boundary (config receipts written to the V26 table). Remaining runtime builders
(retrieval, query tools, chat/memory, daily brief, gates) arrive in later 08A
prompts. No external API access, no writeback, no raw content.
"""

from __future__ import annotations

from .config import SecondBrainConfig, load_second_brain_config
from .contracts import (
    PHASE_08A_CONTRACT_FILES,
    load_all_phase_08a_contracts,
    load_phase_08a_contract,
)
from .reasoning import (
    AdapterResult,
    AnthropicUnavailable,
    ClaudeAdapter,
    ContextEnvelope,
    LiveClaudeAdapter,
    MockClaudeAdapter,
    build_claude_adapter,
)
from .store import read_latest_config_receipt, write_config_receipt

__all__ = [
    "PHASE_08A_CONTRACT_FILES",
    "load_all_phase_08a_contracts",
    "load_phase_08a_contract",
    "SecondBrainConfig",
    "load_second_brain_config",
    "AdapterResult",
    "AnthropicUnavailable",
    "ClaudeAdapter",
    "ContextEnvelope",
    "LiveClaudeAdapter",
    "MockClaudeAdapter",
    "build_claude_adapter",
    "read_latest_config_receipt",
    "write_config_receipt",
]
