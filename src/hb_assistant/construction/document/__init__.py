"""Phase 07C document intelligence (construction).

Promotes SharePoint/OneDrive file intelligence into source-linked, review-controlled
construction document intelligence. This package seed ships the machine-readable
contracts and their loader; materialization, classification, project matching,
controlled extraction, and relationship candidates are added by later 07C prompts.

No raw document text, full paths, signed/download URLs, tokens, or secrets are ever
persisted — only hashed / redacted / bounded fields guarded by CHECK(... = 0) columns.
"""

from __future__ import annotations

from hb_assistant.construction.document.card_materializer import materialize_document_cards
from hb_assistant.construction.document.contracts import (
    DOCUMENT_CONTRACT_FILES,
    load_all_document_contracts,
    load_document_contract,
)
from hb_assistant.construction.document.source_scope import (
    evaluate_source_scope_compliance,
    non_compliant_source_keys,
)

__all__ = [
    "DOCUMENT_CONTRACT_FILES",
    "load_document_contract",
    "load_all_document_contracts",
    "evaluate_source_scope_compliance",
    "non_compliant_source_keys",
    "materialize_document_cards",
]
