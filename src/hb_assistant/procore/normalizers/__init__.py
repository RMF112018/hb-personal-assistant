"""Per-endpoint normalization modules for Procore canonical records.

Each normalizer is a pure function: no I/O, no network, no globals beyond
imports. Callers stamp ``fetched_at`` and supply ``correlation_id``. Output
is a plain ``dict`` that mirrors the row shape consumed by
:func:`hb_assistant.store.repositories.upsert_procore_synced_entity`.

Phase 04 Prompt 04 introduces RFI normalization; subsequent prompts add
Submittal / Observation / Meeting / Daily Log normalizers that mirror this
contract.
"""

from .rfi import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_rfi,
    normalize_rfi_payload_block,
    normalize_rfi_reply,
)

__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_rfi",
    "normalize_rfi_payload_block",
    "normalize_rfi_reply",
]
