"""Phase 06 Prompt 02 — mailbox source registry representation.

Proves the registry builder derives included/excluded folder sources from the
active policy, maps well-known folder names to roles, hashes the mailbox owner
(never stores raw address), and that the folder-source model locks reject any
read-only / no-mutation violation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hb_assistant.construction.policy import (
    EmailIntelligenceActivePolicy,
    MailboxFolderSource,
    build_mailbox_source_registry,
    load_email_intelligence_active_policy,
)


def _policy() -> EmailIntelligenceActivePolicy:
    return load_email_intelligence_active_policy()


def test_builder_maps_included_and_excluded_folders() -> None:
    registry = build_mailbox_source_registry(
        _policy(), mailbox_owner="bobby@example.com"
    )
    by_name = {f.folder_display_name: f for f in registry.folders}

    assert by_name["Inbox"].folder_role == "inbox"
    assert by_name["Sent Items"].folder_role == "sent"
    assert by_name["Archive"].folder_role == "archive"
    for inc in ("Inbox", "Sent Items", "Archive"):
        assert by_name[inc].include_in_sync is True

    for exc in ("Deleted Items", "Junk Email", "Drafts"):
        assert by_name[exc].folder_role == "excluded"
        assert by_name[exc].include_in_sync is False


def test_builder_hashes_owner_and_never_stores_raw_address() -> None:
    owner = "bobby@example.com"
    registry = build_mailbox_source_registry(_policy(), mailbox_owner=owner)
    assert owner not in registry.mailbox_owner_hash
    assert "@" not in registry.mailbox_owner_hash
    assert len(registry.mailbox_owner_hash) >= 8
    # Owner hash is woven into every source_id, still without the raw address.
    for folder in registry.folders:
        assert registry.mailbox_owner_hash in folder.source_id
        assert owner not in folder.source_id


def test_builder_is_deterministic() -> None:
    a = build_mailbox_source_registry(_policy(), mailbox_owner="bobby@example.com")
    b = build_mailbox_source_registry(_policy(), mailbox_owner="bobby@example.com")
    assert a.model_dump() == b.model_dump()


def test_unknown_included_folder_gets_generic_role() -> None:
    policy = _policy().model_copy(update={"include_folders": ["Projects 2025"]})
    registry = build_mailbox_source_registry(policy, mailbox_owner="x@example.com")
    inc = [f for f in registry.folders if f.folder_display_name == "Projects 2025"][0]
    assert inc.folder_role == "included"
    assert inc.include_in_sync is True


def test_empty_owner_hash_rejected() -> None:
    with pytest.raises(ValueError):
        build_mailbox_source_registry(
            _policy(), mailbox_owner="", hasher=lambda _v: None
        )


@pytest.mark.parametrize(
    "field",
    [
        "read_only",
        "mailbox_mutation_allowed",
        "full_archive_crawl_allowed",
        "source_copy_to_vault_allowed",
        "full_email_body_in_obsidian_allowed",
    ],
)
def test_folder_source_locks_reject_violation(field: str) -> None:
    base = {
        "source_id": "outlook:abc:inbox",
        "folder_display_name": "Inbox",
        "folder_role": "inbox",
        "include_in_sync": True,
    }
    # read_only must stay True; the *_allowed flags must stay False.
    base[field] = field != "read_only"
    with pytest.raises(ValidationError):
        MailboxFolderSource.model_validate(base)
