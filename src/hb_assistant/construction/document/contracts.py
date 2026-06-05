"""Phase 07C document-intelligence contract loader.

Loads the machine-readable document-intelligence contracts shipped under
``resources/json/`` (installed in Phase 07C Prompt 02). These contracts are the
single source of truth that later 07C prompts (card materialization, type
classification, project matching, controlled extraction, relationship candidates)
read to stay within the no-raw / review-controlled guardrails.

Loading mirrors the importlib -> filesystem -> empty fallback used by
``construction/data_quality/table_inventory.py`` and ``gates.py`` so the contracts
resolve both from the installed package and from a dev/test checkout.

Read-only: no DB, no network, no raw content. Each contract is identifier/enum
metadata only — it never contains raw document text, URLs, tokens, or secrets.
"""

from __future__ import annotations

import json
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any

_CONTRACT_PKG = "hb_assistant.resources.json"

# Logical contract name -> packaged filename. The keys match each file's "contract"
# field so downstream prompts can request a contract by its stable logical name.
DOCUMENT_CONTRACT_FILES: dict[str, str] = {
    "document_card_contract": "document_card_contract.json",
    "document_classification_contract": "document_classification_contract.json",
    "document_project_match_contract": "document_project_match_contract.json",
    "document_relationship_candidate_contract": "document_relationship_candidate_contract.json",
    "controlled_extraction_contract": "controlled_extraction_contract.json",
}


def _load_json_resource(filename: str) -> dict[str, Any]:
    """Load a packaged json resource. importlib -> filesystem -> empty dict."""
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(_CONTRACT_PKG) / filename).read_text(encoding="utf-8")
        else:  # pragma: no cover - legacy importlib path
            text = importlib_resources.read_text(_CONTRACT_PKG, filename, encoding="utf-8")
        return json.loads(text)
    except Exception:
        candidate = Path(__file__).resolve().parents[2] / "resources" / "json" / filename
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
        return {}


def load_document_contract(name: str) -> dict[str, Any]:
    """Return the parsed document-intelligence contract for ``name``.

    ``name`` is a key of :data:`DOCUMENT_CONTRACT_FILES` (a contract's logical name).
    Raises ``KeyError`` for an unknown contract name.
    """
    if name not in DOCUMENT_CONTRACT_FILES:
        raise KeyError(f"unknown document contract: {name!r}")
    return _load_json_resource(DOCUMENT_CONTRACT_FILES[name])


def load_all_document_contracts() -> dict[str, dict[str, Any]]:
    """Return every document-intelligence contract keyed by its logical name."""
    return {name: load_document_contract(name) for name in DOCUMENT_CONTRACT_FILES}
