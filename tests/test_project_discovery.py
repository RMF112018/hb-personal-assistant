"""Phase 06 Prompt 07 — project-aware discovery service.

Proves discovery matches the live window to pilot projects, previews under
dry-run without persisting, persists email_project_matches + the message project
verdict when committed, propagates thread continuation, scopes to the requested
pilot project, and is idempotent. The fake client exposes only reads.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.email import ProjectEmailDiscovery
from hb_assistant.construction.store import ConstructionStore

_OWNER = "bobby@example.com"


def _msg(mid: str, *, subject: str, conversation_id: str = "conv-1", sender: str = "gc@vendor.com") -> dict[str, Any]:
    return {
        "id": mid,
        "subject": subject,
        "conversationId": conversation_id,
        "internetMessageId": f"<{mid}@x>",
        "from": {"emailAddress": {"address": sender}},
        "toRecipients": [{"emailAddress": {"address": _OWNER}}],
        "ccRecipients": [],
        "bccRecipients": [],
        "receivedDateTime": "2026-05-20T10:00:00Z",
        "hasAttachments": False,
        "bodyPreview": "see attached",
        "webLink": "https://outlook.office.com/x",
    }


class FakeReader:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self._messages = messages

    def get_me(self) -> dict[str, Any]:
        return {"id": "me", "userPrincipalName": _OWNER}

    def list_messages(
        self,
        *,
        folder_id: Optional[str] = None,
        top: int = 50,
        received_after: Optional[str] = None,
        max_items: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        return self._messages[:max_items] if max_items else list(self._messages)


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _store_with_inbox(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="outlook:h:inbox",
        mailbox_owner_hash="h",
        folder_role="inbox",
        folder_display_name="Inbox",
        folder_id="AAMkInbox",
        include_in_sync=True,
    )
    return store


def _match_count(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM email_project_matches").fetchone()[0]
    finally:
        conn.close()


def test_dry_run_matches_without_persisting() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([
        _msg("m1", subject="RFI 23-435-01 slab"),       # number in subject -> tropical 1.0
        _msg("m2", subject="Tropical schedule", conversation_id="conv-2"),  # name -> tropical 0.8
        _msg("m3", subject="lunch plans", conversation_id="conv-3"),        # no match
    ])
    report = ProjectEmailDiscovery(reader, store).discover(project_key="tropical", lookback_days=30, dry_run=True)

    assert report.dry_run is True and report.persisted is False
    assert report.pilot_projects == ["tropical"]
    assert report.messages_scanned == 3
    assert report.matched_messages == 2
    trop = next(p for p in report.projects if p.project_key == "tropical")
    assert trop.matched_messages == 2
    assert trop.by_signal.get("hb_project_number_in_subject") == 1
    assert _match_count(db) == 0  # nothing persisted


def test_commit_persists_matches_and_message_verdict() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([_msg("m1", subject="RFI 23-435-01 slab")])
    ProjectEmailDiscovery(reader, store).discover(project_key="tropical", lookback_days=30, dry_run=False)

    assert _match_count(db) >= 1
    msg = store.get_email_message("m1")
    assert msg is not None
    assert msg["project_number_detected"] == "23-435-01"
    assert msg["project_match_confidence"] == 1.0
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT match_signal, confidence, project_key FROM email_project_matches WHERE message_id='m1'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "hb_project_number_in_subject"
    assert row[1] == 1.0
    assert row[2] == "tropical"


def test_thread_continuation_propagates() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([
        _msg("m1", subject="RFI 23-435-01", conversation_id="conv-A"),       # direct match
        _msg("m2", subject="re: follow up", conversation_id="conv-A"),        # same thread, no direct signal
    ])
    report = ProjectEmailDiscovery(reader, store).discover(project_key="tropical", lookback_days=30, dry_run=False)
    assert report.matched_messages == 2  # m2 inherits via thread continuation
    m2 = store.get_email_message("m2")
    assert m2 is not None and m2["project_match_confidence"] == 0.75
    assert report.signal_counts.get("thread_continuation") == 1


def test_idempotent_recommit() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([_msg("m1", subject="RFI 23-435-01"), _msg("m2", subject="Tropical update", conversation_id="c2")])
    d = ProjectEmailDiscovery(reader, store)
    d.discover(project_key="tropical", lookback_days=30, dry_run=False)
    first = _match_count(db)
    d.discover(project_key="tropical", lookback_days=30, dry_run=False)
    assert _match_count(db) == first  # upsert on (message_id, project_key, match_signal)


def test_no_match_window_persists_nothing() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader([_msg("m1", subject="lunch", conversation_id="c1"), _msg("m2", subject="coffee", conversation_id="c2")])
    report = ProjectEmailDiscovery(reader, store).discover(project_key="tropical", lookback_days=30, dry_run=False)
    assert report.matched_messages == 0
    assert _match_count(db) == 0
