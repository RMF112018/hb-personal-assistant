"""Mailbox source registry representation for Phase 06.

Represents Bobby's mailbox and its included/excluded Outlook folders as
read-only source rows. Built deterministically from the active email policy's
include/exclude folder lists — no Graph call is made here (live folder IDs are
resolved later by folder discovery). The mailbox owner is stored only as a hash;
no raw email address is persisted.

Read-only is locked at the model layer via ``Literal`` fields on
:class:`MailboxFolderSource`; the store adapter and the V10
``email_source_locations`` ``CHECK`` constraints enforce the same flags.
"""

from __future__ import annotations

import re
from typing import Callable, List, Literal, Optional

from pydantic import BaseModel

from hb_assistant.normalize.redaction import hash_value

from .email_active import EmailIntelligenceActivePolicy

FolderRole = Literal["inbox", "sent", "archive", "included", "excluded"]

# Known Outlook well-known folder display names → canonical role.
_ROLE_BY_DISPLAY_NAME: dict[str, FolderRole] = {
    "inbox": "inbox",
    "sent items": "sent",
    "archive": "archive",
}


class MailboxFolderSource(BaseModel):
    """A single mailbox folder source row (read-only, metadata-only)."""

    source_id: str
    folder_display_name: str
    folder_role: FolderRole
    include_in_sync: bool
    folder_id: Optional[str] = None  # resolved later by live folder discovery

    # Hard guardrails (locked at the model layer).
    read_only: Literal[True] = True
    mailbox_mutation_allowed: Literal[False] = False
    full_archive_crawl_allowed: Literal[False] = False
    source_copy_to_vault_allowed: Literal[False] = False
    full_email_body_in_obsidian_allowed: Literal[False] = False

    model_config = {"extra": "forbid"}


class MailboxSourceRegistry(BaseModel):
    """Bobby's mailbox + its included/excluded folder sources."""

    mailbox_owner_hash: str
    mailbox_display_name_redacted: Optional[str] = None
    source_system: Literal["outlook"] = "outlook"
    folders: List[MailboxFolderSource]

    model_config = {"extra": "forbid"}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "folder"


def build_mailbox_source_registry(
    policy: EmailIntelligenceActivePolicy,
    *,
    mailbox_owner: str,
    mailbox_display_name_redacted: Optional[str] = None,
    hasher: Callable[[Optional[str]], Optional[str]] = hash_value,
) -> MailboxSourceRegistry:
    """Derive a mailbox source registry from the active policy folder lists.

    ``mailbox_owner`` (e.g. a UPN) is hashed — never stored raw.
    ``mailbox_display_name_redacted`` must already be redacted by the caller.
    Included folders get ``include_in_sync=True`` with a role mapped from the
    well-known display name; excluded folders get role ``excluded`` and
    ``include_in_sync=False``.
    """
    owner_hash = hasher(mailbox_owner)
    if not owner_hash:
        raise ValueError("mailbox_owner must hash to a non-empty value")

    folders: List[MailboxFolderSource] = []
    for name in policy.include_folders:
        role = _ROLE_BY_DISPLAY_NAME.get(name.strip().lower(), "included")
        folders.append(
            MailboxFolderSource(
                source_id=f"outlook:{owner_hash}:{_slug(name)}",
                folder_display_name=name,
                folder_role=role,
                include_in_sync=True,
            )
        )
    for name in policy.exclude_folders:
        folders.append(
            MailboxFolderSource(
                source_id=f"outlook:{owner_hash}:{_slug(name)}",
                folder_display_name=name,
                folder_role="excluded",
                include_in_sync=False,
            )
        )

    return MailboxSourceRegistry(
        mailbox_owner_hash=owner_hash,
        mailbox_display_name_redacted=mailbox_display_name_redacted,
        folders=folders,
    )
