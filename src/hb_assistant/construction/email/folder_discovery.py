"""Phase 06 — Outlook/Exchange folder discovery + sync-state initialization.

Resolves the policy-driven mailbox source registry (included Inbox / Sent Items /
Archive; excluded Deleted Items / Junk Email / Drafts) against the **live**
mailbox via the read-only Graph mail client, then persists the resolved
``email_source_locations`` and initializes one bounded-lookback ``email_sync_state``
cursor per included folder.

Read-only and metadata-only: only `get_me` / `list_mail_folders` (guarded GETs)
are issued, and the only writes are local SQLite rows (the store adapter + SQLite
CHECK constraints reject any non-read-only flag). ``dry_run`` (the default)
resolves and previews without touching the database.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.policy import (
    EmailIntelligenceActivePolicy,
    build_mailbox_source_registry,
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.mail_readonly_client import ReadOnlyMailClient
from hb_assistant.normalize.redaction import hash_value

_SYNC_MODE = "bounded_lookback"
_INITIAL_SYNC_STATUS = "pending"


class DiscoveredFolder(BaseModel):
    """A single resolved (or unresolved) folder source — metadata only."""

    source_id: str
    folder_role: str
    folder_display_name: str
    include_in_sync: bool
    matched: bool
    folder_id_fingerprint: Optional[str] = None
    total_item_count: Optional[int] = None
    unread_item_count: Optional[int] = None

    model_config = {"extra": "forbid"}


class FolderDiscoveryResult(BaseModel):
    """Outcome of a folder-discovery run (no tokens, no raw folder ids)."""

    mailbox_owner_upn: Optional[str] = None
    mailbox_owner_hash: str
    source_system: str = "outlook"
    dry_run: bool
    persisted: bool
    default_lookback_days: int
    folders: list[DiscoveredFolder]
    included_matched: int
    excluded_matched: int
    unmatched_policy_folders: list[str]
    other_folders_count: int

    model_config = {"extra": "forbid"}


class EmailFolderDiscovery:
    """Resolve + persist mailbox folder sources and per-folder sync state."""

    def __init__(self, mail_client: ReadOnlyMailClient, store: ConstructionStore) -> None:
        self._mail = mail_client
        self._store = store

    def discover(
        self,
        *,
        policy: Optional[EmailIntelligenceActivePolicy] = None,
        dry_run: bool = True,
    ) -> FolderDiscoveryResult:
        policy = policy or load_email_intelligence_active_policy()

        me = self._mail.get_me()
        upn = me.get("userPrincipalName") or me.get("mail")
        if not upn:
            raise ValueError("mailbox owner UPN/mail not present on /me response")

        registry = build_mailbox_source_registry(policy, mailbox_owner=upn)

        live = self._mail.list_mail_folders(top=100, max_items=200)
        live_by_name: dict[str, dict[str, Any]] = {}
        for folder in live:
            name = folder.get("displayName")
            if isinstance(name, str):
                live_by_name.setdefault(name.strip().lower(), folder)

        discovered: list[DiscoveredFolder] = []
        unmatched: list[str] = []
        matched_names: set[str] = set()

        for source in registry.folders:
            key = source.folder_display_name.strip().lower()
            live_folder = live_by_name.get(key)
            matched = live_folder is not None
            folder_id = live_folder.get("id") if live_folder else None
            if matched:
                matched_names.add(key)
            else:
                unmatched.append(source.folder_display_name)

            discovered.append(
                DiscoveredFolder(
                    source_id=source.source_id,
                    folder_role=source.folder_role,
                    folder_display_name=source.folder_display_name,
                    include_in_sync=source.include_in_sync,
                    matched=matched,
                    folder_id_fingerprint=hash_value(folder_id) if folder_id else None,
                    total_item_count=(live_folder or {}).get("totalItemCount"),
                    unread_item_count=(live_folder or {}).get("unreadItemCount"),
                )
            )

            if matched and not dry_run:
                self._persist(source, live_folder, registry.mailbox_owner_hash, upn, policy)

        other_folders_count = sum(1 for name in live_by_name if name not in matched_names)
        included_matched = sum(1 for d in discovered if d.include_in_sync and d.matched)
        excluded_matched = sum(1 for d in discovered if not d.include_in_sync and d.matched)

        return FolderDiscoveryResult(
            mailbox_owner_upn=upn,
            mailbox_owner_hash=registry.mailbox_owner_hash,
            source_system=registry.source_system,
            dry_run=dry_run,
            persisted=not dry_run,
            default_lookback_days=policy.default_lookback_days,
            folders=discovered,
            included_matched=included_matched,
            excluded_matched=excluded_matched,
            unmatched_policy_folders=unmatched,
            other_folders_count=other_folders_count,
        )

    def _persist(
        self,
        source: Any,
        live_folder: dict[str, Any],
        owner_hash: str,
        upn: str,
        policy: EmailIntelligenceActivePolicy,
    ) -> None:
        folder_id = live_folder["id"]
        self._store.upsert_email_source_location(
            source_id=source.source_id,
            mailbox_owner_hash=owner_hash,
            folder_role=source.folder_role,
            folder_display_name=source.folder_display_name,
            folder_id=folder_id,
            mailbox_user_principal_name_hash=hash_value(upn),
            source_system="outlook",
            include_in_sync=source.include_in_sync,
            sync_mode=_SYNC_MODE,
            default_lookback_days=policy.default_lookback_days,
        )
        # Only included folders get a sync cursor; excluded folders are recorded
        # (include_in_sync=0) but never synced.
        if source.include_in_sync:
            self._store.upsert_email_sync_state(
                source_id=source.source_id,
                folder_id=folder_id,
                sync_mode=_SYNC_MODE,
                lookback_days=policy.default_lookback_days,
                sync_status=_INITIAL_SYNC_STATUS,
            )
