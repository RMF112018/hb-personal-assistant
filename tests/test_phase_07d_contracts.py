"""Phase 07D Prompt 02 — relationship/meeting-prep contracts and policy seeds.

Proves the eight 07D JSON contracts and five YAML policy seeds load from the package
(importlib -> filesystem), expose their stable version/identifier metadata and required
fields, encode the no-auto-promotion rules for weak/model/sensitive relationships, and
contain no raw content, URL, address, token, or secret value (identifier/enum only).
"""

from __future__ import annotations

import json
import re

import pytest

from hb_assistant.construction.relationships.contracts import (
    PHASE_07D_CONTRACT_FILES,
    PHASE_07D_SEED_FILES,
    load_all_phase_07d_contracts,
    load_all_phase_07d_seeds,
    load_phase_07d_contract,
    load_phase_07d_seed,
)

# A leak-pattern probe: URLs, email/host addresses, calendar bodies, PEM/token markers.
_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}",
    re.IGNORECASE,
)

# Contracts that carry a "version" field. The validation matrix is identified by "phase".
_VERSIONED_CONTRACTS = set(PHASE_07D_CONTRACT_FILES) - {"phase_07d_validation_matrix"}

_REQUIRED_KEYS = {
    "cross_source_relationship_contract": ["version", "required_fields", "confidence_classes", "no_auto_promotion_for"],
    "source_evidence_trail_contract": ["version", "required_fields", "guardrails"],
    "meeting_prep_brief_contract": ["version", "required_fields", "guardrails"],
    "project_issue_history_contract": ["version", "required_fields", "guardrails"],
    "risk_digest_contract": ["version", "required_fields", "guardrails"],
    "aging_exposure_report_contract": ["version", "required_fields", "guardrails"],
    "phase_07d_data_quality_gates": ["version", "required_fields", "guardrails"],
    "phase_07d_validation_matrix": ["phase", "evidence_root", "commands", "stop_on"],
}


def test_all_contracts_and_seeds_load() -> None:
    contracts = load_all_phase_07d_contracts()
    seeds = load_all_phase_07d_seeds()
    assert set(contracts) == set(PHASE_07D_CONTRACT_FILES)
    assert set(seeds) == set(PHASE_07D_SEED_FILES)
    # every contract/seed loaded to a non-empty mapping
    for name, c in contracts.items():
        assert c, f"contract {name} loaded empty"
    for name, s in seeds.items():
        assert s, f"seed {name} loaded empty"


@pytest.mark.parametrize("name", sorted(_VERSIONED_CONTRACTS))
def test_versioned_contracts_have_version(name: str) -> None:
    assert load_phase_07d_contract(name).get("version"), f"{name} missing version"


@pytest.mark.parametrize("name", sorted(PHASE_07D_SEED_FILES))
def test_seeds_have_version(name: str) -> None:
    assert load_phase_07d_seed(name).get("version"), f"{name} missing version"


@pytest.mark.parametrize("name", sorted(PHASE_07D_CONTRACT_FILES))
def test_required_keys_present(name: str) -> None:
    c = load_phase_07d_contract(name)
    for key in _REQUIRED_KEYS[name]:
        assert key in c, f"{name} missing required key {key}"


def test_relationship_contract_blocks_weak_model_sensitive_promotion() -> None:
    c = load_phase_07d_contract("cross_source_relationship_contract")
    blocked = set(c["no_auto_promotion_for"])
    assert {"weak_heuristic", "model_proposed", "sensitive_high_impact"} <= blocked
    # the relationship policy seed agrees: those classes are never locally promoted
    policy = load_phase_07d_seed("cross_source_relationship_policy")
    assert policy["promotion"]["weak_heuristic"]["allow_local_promotion"] is False
    assert policy["promotion"]["model_proposed"]["allow_local_promotion"] is False
    assert policy["promotion"]["sensitive_high_impact"]["allow_local_promotion"] is False
    # deterministic is the only class allowed local promotion, and only without high-impact
    assert policy["promotion"]["deterministic"]["allow_local_promotion"] is True
    assert policy["promotion"]["deterministic"]["require_sensitive_high_impact_absent"] is True


def test_review_rules_seed_lists_sensitive_categories() -> None:
    rules = load_phase_07d_seed("review_required_relationship_rules")
    cats = set(rules["always_review_required"]["categories"])
    assert {"legal", "contractual", "claim", "safety", "personnel", "financial"} <= cats
    classes = set(rules["always_review_required"]["confidence_classes"])
    assert {"weak_heuristic", "model_proposed"} <= classes


@pytest.mark.parametrize("name", sorted(PHASE_07D_CONTRACT_FILES))
def test_contracts_are_identifier_only_no_leaks(name: str) -> None:
    blob = json.dumps(load_phase_07d_contract(name))
    assert not _LEAK.search(blob), f"{name} contains a leak-pattern value"


@pytest.mark.parametrize("name", sorted(PHASE_07D_SEED_FILES))
def test_seeds_are_identifier_only_no_leaks(name: str) -> None:
    blob = json.dumps(load_phase_07d_seed(name))
    assert not _LEAK.search(blob), f"{name} contains a leak-pattern value"


def test_unknown_names_raise() -> None:
    with pytest.raises(KeyError):
        load_phase_07d_contract("nope")
    with pytest.raises(KeyError):
        load_phase_07d_seed("nope")
