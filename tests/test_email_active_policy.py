"""Phase 06 Prompt 02 — active email-intelligence policy (model + loader locks).

Proves the Pydantic ``Literal`` locks reject any attempt to loosen the read-only
/ metadata-only guardrails, that unknown fields are forbidden, and that the
seeded policy loads cleanly. The deferred policy is untouched.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from hb_assistant.construction.policy import (
    EmailIntelligenceActivePolicy,
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.policy.email_active import _resolve_seed_path


def _valid_data() -> dict:
    return {
        "mailbox_mode": "read_only",
        "writeback_allowed": False,
        "mailbox_mutation_allowed": False,
        "full_archive_crawl": False,
        "source_copy_to_vault": False,
        "full_email_body_in_obsidian": False,
        "attachment_content_download_by_default": False,
        "metadata_only_by_default": True,
        "review_required_for_sensitive": True,
        "initial_backfill_mode": "pilot_projects_only",
        "ollama_invalid_json_routes_to_review": True,
        "default_lookback_days": 30,
        "include_folders": ["Inbox", "Sent Items", "Archive"],
        "exclude_folders": ["Deleted Items", "Junk Email", "Drafts"],
        "ollama_enabled_for_email_intelligence": True,
        "low_confidence_threshold": 0.75,
    }


def test_valid_active_policy_constructs() -> None:
    policy = EmailIntelligenceActivePolicy.model_validate(_valid_data())
    assert policy.mailbox_mode == "read_only"
    assert policy.include_folders == ["Inbox", "Sent Items", "Archive"]
    assert policy.exclude_folders == ["Deleted Items", "Junk Email", "Drafts"]


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("mailbox_mode", "read_write"),
        ("writeback_allowed", True),
        ("mailbox_mutation_allowed", True),
        ("full_archive_crawl", True),
        ("source_copy_to_vault", True),
        ("full_email_body_in_obsidian", True),
        ("attachment_content_download_by_default", True),
        ("metadata_only_by_default", False),
        ("review_required_for_sensitive", False),
        ("initial_backfill_mode", "full_mailbox"),
        ("ollama_invalid_json_routes_to_review", False),
    ],
)
def test_locked_fields_reject_loosening(field: str, bad_value: object) -> None:
    data = _valid_data()
    data[field] = bad_value
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


def test_unknown_field_forbidden() -> None:
    data = _valid_data()
    data["secret_writeback_override"] = True
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


@pytest.mark.parametrize("bad_lookback", [0, -1, 400])
def test_lookback_must_be_bounded(bad_lookback: int) -> None:
    data = _valid_data()
    data["default_lookback_days"] = bad_lookback
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


@pytest.mark.parametrize("bad_threshold", [-0.1, 1.5])
def test_threshold_must_be_in_unit_range(bad_threshold: float) -> None:
    data = _valid_data()
    data["low_confidence_threshold"] = bad_threshold
    with pytest.raises(ValidationError):
        EmailIntelligenceActivePolicy.model_validate(data)


def test_seed_loads_and_locks() -> None:
    policy = load_email_intelligence_active_policy()
    assert policy.mailbox_mode == "read_only"
    assert policy.writeback_allowed is False
    assert policy.mailbox_mutation_allowed is False
    assert policy.full_email_body_in_obsidian is False
    assert policy.attachment_content_download_by_default is False
    assert policy.metadata_only_by_default is True
    assert policy.review_required_for_sensitive is True
    assert policy.initial_backfill_mode == "pilot_projects_only"


def test_seed_file_content_matches_locks() -> None:
    # The on-disk seed must itself satisfy every lock (no drift).
    seed = _resolve_seed_path()
    data = yaml.safe_load(seed.read_text(encoding="utf-8"))
    assert data["mailbox_mode"] == "read_only"
    assert data["writeback_allowed"] is False
    assert data["mailbox_mutation_allowed"] is False
    assert data["full_email_body_in_obsidian"] is False
    assert data["attachment_content_download_by_default"] is False
    assert data["initial_backfill_mode"] == "pilot_projects_only"


def test_explicit_override_path_wins(tmp_path) -> None:
    override = tmp_path / "override.yml"
    data = _valid_data()
    data["default_lookback_days"] = 14
    override.write_text(yaml.safe_dump(data), encoding="utf-8")
    policy = load_email_intelligence_active_policy(override_path=override)
    assert policy.default_lookback_days == 14
