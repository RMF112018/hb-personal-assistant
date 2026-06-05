"""Phase 07C Prompt 02 — document-intelligence contract loader.

Proves the five machine-readable document contracts ship, load via the package
loader, declare the expected version, and carry identifier/enum metadata only
(no raw document text, URLs, tokens, or secrets).
"""

from __future__ import annotations

import re

import pytest

from hb_assistant.construction.document import (
    DOCUMENT_CONTRACT_FILES,
    load_all_document_contracts,
    load_document_contract,
)

_EXPECTED_CONTRACTS = {
    "document_card_contract",
    "document_classification_contract",
    "document_project_match_contract",
    "document_relationship_candidate_contract",
    "controlled_extraction_contract",
}

# Top-level keys each contract must expose for downstream 07C prompts.
_REQUIRED_KEYS = {
    "document_card_contract": ["required_fields", "forbidden_fields", "guardrail_columns"],
    "document_classification_contract": ["document_types", "signal_order", "model_output_policy"],
    "document_project_match_contract": ["confidence_classes", "review_required_classes"],
    "document_relationship_candidate_contract": ["target_systems", "target_record_types"],
    "controlled_extraction_contract": ["persist_allowed", "blocked_when"],
}

_LEAK = re.compile(r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN", re.IGNORECASE)


def test_registry_matches_expected_contract_set() -> None:
    assert set(DOCUMENT_CONTRACT_FILES) == _EXPECTED_CONTRACTS


def test_all_contracts_load_with_version_and_self_name() -> None:
    contracts = load_all_document_contracts()
    assert set(contracts) == _EXPECTED_CONTRACTS
    for name, c in contracts.items():
        assert c, f"{name} loaded empty"
        assert c["version"] == "phase07c-v1", name
        assert c["contract"] == name, name


@pytest.mark.parametrize("name", sorted(_EXPECTED_CONTRACTS))
def test_required_keys_present(name: str) -> None:
    c = load_document_contract(name)
    for key in _REQUIRED_KEYS[name]:
        assert key in c, f"{name} missing required key {key}"


def test_card_contract_forbids_raw_and_url_fields() -> None:
    c = load_document_contract("document_card_contract")
    forbidden = set(c["forbidden_fields"])
    # the card contract must explicitly forbid raw text / URL / payload field families
    assert {"raw_document_text", "signed_url", "download_url", "raw_payload"} <= forbidden
    # auto-promotion of project matches must be disabled
    assert (
        load_document_contract("document_project_match_contract")["auto_promotion_allowed"] is False
    )
    # controlled extraction must not persist full text by default
    ce = load_document_contract("controlled_extraction_contract")
    assert ce["persist_full_text"] is False
    assert ce["download_default"] is False and ce["extract_default"] is False


@pytest.mark.parametrize("name", sorted(_EXPECTED_CONTRACTS))
def test_contracts_are_identifier_only_no_leaks(name: str) -> None:
    """The contracts list field/enum *names* only — never a raw value, URL, or secret."""
    import json

    blob = json.dumps(load_document_contract(name))
    assert not _LEAK.search(blob), f"{name} contains a leak-pattern value"


def test_unknown_contract_raises() -> None:
    with pytest.raises(KeyError):
        load_document_contract("nope_not_a_contract")
