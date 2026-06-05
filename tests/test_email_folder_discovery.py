"""Phase 06 Prompt 05 — email folder discovery + sync-state persistence.

Proves discovery resolves the policy registry against a live mailbox listing,
previews under dry-run without touching the DB, and (when committed) persists
email_source_locations for all matched folders plus an email_sync_state cursor
for included folders only. Read-only: the fake client exposes only reads.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.email import EmailFolderDiscovery
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

_UPN = "bobby@example.com"

# Standard Outlook top-level folders (metadata only).
_FULL_MAILBOX = [
    {"id": "AAMkInbox", "displayName": "Inbox", "totalItemCount": 42, "unreadItemCount": 3},
    {"id": "AAMkSent", "displayName": "Sent Items", "totalItemCount": 128, "unreadItemCount": 0},
    {"id": "AAMkArchive", "displayName": "Archive", "totalItemCount": 3000, "unreadItemCount": 0},
    {
        "id": "AAMkDeleted",
        "displayName": "Deleted Items",
        "totalItemCount": 15,
        "unreadItemCount": 0,
    },
    {"id": "AAMkJunk", "displayName": "Junk Email", "totalItemCount": 2, "unreadItemCount": 1},
    {"id": "AAMkDrafts", "displayName": "Drafts", "totalItemCount": 0, "unreadItemCount": 0},
    {"id": "AAMkProjects", "displayName": "Projects", "totalItemCount": 9, "unreadItemCount": 0},
]


class FakeReader:
    """Read-only mail client stand-in (get_me + list_mail_folders only)."""

    def __init__(self, folders: list[dict[str, Any]], upn: str = _UPN) -> None:
        self._folders = folders
        self._upn = upn

    def get_me(self) -> dict[str, Any]:
        return {"id": "me-id", "userPrincipalName": self._upn, "displayName": "Bobby"}

    def list_mail_folders(
        self, *, top: int = 25, max_items: Optional[int] = None
    ) -> list[dict[str, Any]]:
        return list(self._folders)


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _discovery(folders: list[dict[str, Any]]) -> tuple[EmailFolderDiscovery, ConstructionStore]:
    store = ConstructionStore(_tmp_db())
    return EmailFolderDiscovery(FakeReader(folders), store), store  # type: ignore[arg-type]


def test_dry_run_resolves_roles_without_persisting() -> None:
    discovery, store = _discovery(_FULL_MAILBOX)
    result = discovery.discover(dry_run=True)

    assert result.dry_run is True
    assert result.persisted is False
    assert result.mailbox_owner_hash == hash_value(_UPN)

    by_role = {f.folder_role: f for f in result.folders}
    assert by_role["inbox"].include_in_sync is True
    assert by_role["sent"].include_in_sync is True
    assert by_role["archive"].include_in_sync is True
    # excluded folders all carry role "excluded" and include_in_sync False
    excluded = [f for f in result.folders if not f.include_in_sync]
    assert {f.folder_display_name for f in excluded} == {"Deleted Items", "Junk Email", "Drafts"}
    assert all(f.matched for f in result.folders)
    assert result.included_matched == 3
    assert result.excluded_matched == 3
    # "Projects" is neither included nor excluded.
    assert result.other_folders_count == 1

    # Nothing persisted in dry-run.
    assert store.list_email_source_locations() == []


def test_commit_persists_sources_and_sync_state() -> None:
    discovery, store = _discovery(_FULL_MAILBOX)
    result = discovery.discover(dry_run=False)
    assert result.persisted is True

    rows = store.list_email_source_locations()
    assert len(rows) == 6  # 3 included + 3 excluded
    by_role = {r["folder_role"]: r for r in rows}
    assert by_role["inbox"]["include_in_sync"] is True
    assert by_role["inbox"]["folder_id"] == "AAMkInbox"
    assert by_role["excluded"]["include_in_sync"] is False
    assert by_role["inbox"]["mailbox_owner_hash"] == hash_value(_UPN)
    assert by_role["inbox"]["default_lookback_days"] == 30

    # Included folders get a pending sync cursor; excluded do not.
    included = [f for f in result.folders if f.include_in_sync]
    for f in included:
        state = store.get_email_sync_state(
            source_id=f.source_id, folder_id=_folder_id_for(f.folder_role)
        )
        assert state is not None
        assert state["sync_status"] == "pending"
        assert state["sync_mode"] == "bounded_lookback"

    # Excluded folders are recorded but never get a sync cursor.
    excluded_ids = {"excluded": ["AAMkDeleted", "AAMkJunk", "AAMkDrafts"]}
    excluded = [f for f in result.folders if not f.include_in_sync]
    for f in excluded:
        for fid in excluded_ids["excluded"]:
            assert store.get_email_sync_state(source_id=f.source_id, folder_id=fid) is None


def _folder_id_for(role: str) -> str:
    return {"inbox": "AAMkInbox", "sent": "AAMkSent", "archive": "AAMkArchive"}[role]


def test_archive_missing_is_unmatched_and_not_persisted() -> None:
    mailbox = [f for f in _FULL_MAILBOX if f["displayName"] != "Archive"]
    discovery, store = _discovery(mailbox)
    result = discovery.discover(dry_run=False)

    archive = next(f for f in result.folders if f.folder_role == "archive")
    assert archive.matched is False
    assert archive.folder_id_fingerprint is None
    assert "Archive" in result.unmatched_policy_folders
    assert result.included_matched == 2  # inbox + sent only

    rows = store.list_email_source_locations()
    # Archive not persisted (could not resolve a live folder id).
    assert all(r["folder_role"] != "archive" for r in rows)
    assert len(rows) == 5


def test_idempotent_recommit_updates_in_place() -> None:
    discovery, store = _discovery(_FULL_MAILBOX)
    discovery.discover(dry_run=False)
    discovery.discover(dry_run=False)  # re-run must not duplicate rows
    assert len(store.list_email_source_locations()) == 6
