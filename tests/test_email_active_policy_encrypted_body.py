"""Phase 06 Prompt 08A — active policy encrypted-body fields + locks."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hb_assistant.construction.policy import load_email_intelligence_active_policy
from hb_assistant.construction.policy.email_active import EmailIntelligenceActivePolicy


def _valid() -> dict:
    return load_email_intelligence_active_policy().model_dump()


def test_seed_allows_encrypted_body_storage() -> None:
    p = load_email_intelligence_active_policy()
    assert p.full_body_storage_allowed is True
    assert p.full_body_storage_mode == "encrypted_text_vault"
    assert p.plaintext_body_persistence_allowed is False
    assert p.max_full_body_fetch_per_run == 100


@pytest.mark.parametrize(
    "field",
    [
        "plaintext_body_persistence_allowed",
        "obsidian_full_body_allowed",
        "evidence_full_body_allowed",
        "log_full_body_allowed",
        "attachment_content_storage_allowed",
        "mailbox_mutation_allowed",
        "writeback_allowed",
        "full_email_body_in_obsidian",
    ],
)
def test_locked_false_fields_cannot_be_true(field: str) -> None:
    data = _valid()
    data[field] = True
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


def test_storage_mode_cannot_be_plaintext() -> None:
    data = _valid()
    data["full_body_storage_mode"] = "plaintext"
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


def test_broad_full_body_cannot_bypass_encrypted_mode() -> None:
    # Even with full_body_storage_allowed True, the mode is locked to the vault.
    data = _valid()
    data["full_body_storage_allowed"] = True
    data["full_body_storage_mode"] = "raw_sqlite"
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


def test_review_for_sensitive_cannot_be_disabled() -> None:
    data = _valid()
    data["encrypted_body_requires_review_for_sensitive"] = False
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


@pytest.mark.parametrize("bad", [0, 1001, -5])
def test_body_fetch_cap_is_bounded(bad: int) -> None:
    data = _valid()
    data["max_full_body_fetch_per_run"] = bad
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


def test_unknown_fields_rejected() -> None:
    data = _valid()
    data["secret_plaintext_override"] = True
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)
