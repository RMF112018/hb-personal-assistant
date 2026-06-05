"""Phase 06 Prompt 06 — bounded message metadata indexing.

Proves the indexer normalizes redacted metadata, persists messages/recipients/
attachment metadata, derives thread_key per the schema doc, flags the owner
(is_bobby), is idempotent across re-runs, and writes nothing in dry-run. The fake
client exposes only reads.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.email import EmailMessageIndexer
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

_OWNER = "bobby@example.com"


def _msg(
    mid: str,
    *,
    subject: str = "RFI 12",
    conversation_id: Optional[str] = "conv-1",
    internet_message_id: Optional[str] = None,
    sender: str = "pm@vendor.com",
    to: Optional[list[str]] = None,
    cc: Optional[list[str]] = None,
    has_attachments: bool = False,
) -> dict[str, Any]:
    def _rcpts(addrs: Optional[list[str]]) -> list[dict[str, Any]]:
        return [{"emailAddress": {"address": a}} for a in (addrs or [])]

    return {
        "id": mid,
        "subject": subject,
        "conversationId": conversation_id,
        "internetMessageId": internet_message_id,
        "from": {"emailAddress": {"address": sender}},
        "toRecipients": _rcpts(to or [_OWNER]),
        "ccRecipients": _rcpts(cc),
        "bccRecipients": [],
        "receivedDateTime": "2026-05-20T10:00:00Z",
        "sentDateTime": "2026-05-20T09:59:00Z",
        "hasAttachments": has_attachments,
        "importance": "normal",
        "categories": ["Blue"],
        "sensitivity": "normal",
        "webLink": "https://outlook.office.com/x",
        "bodyPreview": "Please review the attached RFI response for the tropical project.",
    }


class FakeReader:
    """Read-only mail client stand-in for the indexer."""

    def __init__(
        self,
        by_folder: dict[str, list[dict[str, Any]]],
        attachments: Optional[dict[str, list]] = None,
    ) -> None:
        self._by_folder = by_folder
        self._attachments = attachments or {}
        self.attachment_calls: list[str] = []

    def get_me(self) -> dict[str, Any]:
        return {"id": "me", "userPrincipalName": _OWNER, "displayName": "Bobby"}

    def list_messages(
        self,
        *,
        folder_id: Optional[str] = None,
        top: int = 50,
        received_after: Optional[str] = None,
        max_items: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        msgs = self._by_folder.get(folder_id or "", [])
        return msgs[:max_items] if max_items else list(msgs)

    def list_attachment_metadata(self, message_id: str) -> list[dict[str, Any]]:
        self.attachment_calls.append(message_id)
        return list(self._attachments.get(message_id, []))


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


def _counts(db: str) -> dict[str, int]:
    conn = sqlite3.connect(db)
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in (
                "email_messages",
                "email_message_recipients",
                "email_message_attachments",
                "email_crawl_runs",
            )
        }
    finally:
        conn.close()


def test_index_persists_messages_recipients_attachments() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(
        by_folder={
            "AAMkInbox": [_msg("m1", has_attachments=True), _msg("m2", cc=["foo@hbcc.com"])]
        },
        attachments={
            "m1": [{"id": "a1", "name": "rfi.pdf", "contentType": "application/pdf", "size": 2048}]
        },
    )
    result = EmailMessageIndexer(reader, store).index(project_key="tropical", lookback_days=30)

    assert result.persisted is True
    assert result.messages_indexed == 2
    c = _counts(db)
    assert c["email_messages"] == 2
    assert c["email_message_attachments"] == 1

    m1 = store.get_email_message("m1")
    assert m1 is not None
    assert m1["full_body_persisted"] is False
    assert m1["extraction_policy"] == "metadata_only"
    assert m1["thread_key"] == "conv-1"  # conversation_id used directly
    assert m1["has_attachments"] is True
    # subject is redacted, not stored raw
    assert "RFI 12" not in (m1["subject_redacted"] or "")
    assert m1["subject_hash"] == hash_value("RFI 12")


def test_owner_recipient_flagged_is_bobby() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(by_folder={"AAMkInbox": [_msg("m1", to=[_OWNER, "other@vendor.com"])]})
    EmailMessageIndexer(reader, store).index(lookback_days=30)
    recips = store.list_email_message_recipients("m1")
    owner_rows = [r for r in recips if r["address_hash"] == hash_value(_OWNER)]
    assert owner_rows and all(r["is_bobby"] for r in owner_rows)
    other = [r for r in recips if r["domain"] == "vendor.com"]
    assert other and not any(r["is_bobby"] for r in other)


def test_thread_key_falls_back_to_hash_when_no_conversation() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(
        by_folder={"AAMkInbox": [_msg("m1", conversation_id=None, internet_message_id="<abc@x>")]}
    )
    EmailMessageIndexer(reader, store).index(lookback_days=30)
    m1 = store.get_email_message("m1")
    assert m1 is not None
    assert m1["thread_key"] == hash_value("<abc@x>")
    assert m1["conversation_id"] is None


def test_index_is_idempotent() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(
        by_folder={"AAMkInbox": [_msg("m1", has_attachments=True), _msg("m2")]},
        attachments={
            "m1": [{"id": "a1", "name": "x.pdf", "contentType": "application/pdf", "size": 10}]
        },
    )
    indexer = EmailMessageIndexer(reader, store)
    indexer.index(lookback_days=30)
    first = _counts(db)
    indexer.index(lookback_days=30)
    second = _counts(db)

    # Message/recipient/attachment rows are stable (upserts); only crawl runs accumulate.
    assert second["email_messages"] == first["email_messages"] == 2
    assert second["email_message_recipients"] == first["email_message_recipients"]
    assert second["email_message_attachments"] == first["email_message_attachments"] == 1
    assert second["email_crawl_runs"] > first["email_crawl_runs"]


def test_dry_run_writes_no_message_rows() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(by_folder={"AAMkInbox": [_msg("m1"), _msg("m2")]})
    result = EmailMessageIndexer(reader, store).index(lookback_days=30, dry_run=True)
    assert result.persisted is False
    assert result.messages_seen == 2
    assert result.messages_indexed == 0
    c = _counts(db)
    assert c["email_messages"] == 0
    assert c["email_crawl_runs"] == 0


def test_max_messages_per_folder_is_bounded() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(by_folder={"AAMkInbox": [_msg(f"m{i}") for i in range(10)]})
    result = EmailMessageIndexer(reader, store).index(lookback_days=30, max_messages_per_folder=3)
    assert result.messages_indexed == 3
    assert _counts(db)["email_messages"] == 3


# --- Prompt 08: attachment enrichment ---------------------------------------


def _enrich_counts(db: str) -> dict[str, int]:
    conn = sqlite3.connect(db)
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in (
                "email_message_attachments",
                "email_relationship_candidates",
                "email_review_queue",
            )
        }
    finally:
        conn.close()


def test_attachment_enrichment_link_sensitivity_and_candidates() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(
        by_folder={"AAMkInbox": [_msg("m1", has_attachments=True)]},
        attachments={
            "m1": [
                {
                    "id": "a1",
                    "name": "Subcontract Agreement.pdf",
                    "contentType": "application/pdf",
                    "size": 2048,
                },
                {
                    "id": "a2",
                    "name": "logo.png",
                    "contentType": "image/png",
                    "size": 10,
                    "isInline": True,
                },
            ]
        },
    )
    result = EmailMessageIndexer(reader, store).index(project_key="tropical", lookback_days=30)

    assert result.attachments_indexed == 2
    assert result.sensitive_attachments == 1
    assert result.source_link_candidates >= 1
    assert result.review_items_created >= 1

    conn = sqlite3.connect(db)
    try:
        # The contract attachment is flagged sensitive + review_required; name is redacted.
        row = conn.execute(
            "SELECT name_redacted, sensitivity_hint, review_required, content_downloaded, metadata_only "
            "FROM email_message_attachments WHERE attachment_key='m1:a1'"
        ).fetchone()
        assert row[1] == "contracts"
        assert row[2] == 1  # review_required
        assert row[3] == 0  # content_downloaded never set
        assert row[4] == 1  # metadata_only locked
        assert "Subcontract" not in (row[0] or "")
        # A SharePoint source-link candidate exists for the document.
        cand = conn.execute(
            "SELECT candidate_type, target_source_system FROM email_relationship_candidates "
            "WHERE message_id='m1' AND match_signal='attachment_filename'"
        ).fetchone()
        assert cand == ("sharepoint_drive_item", "sharepoint")
        # The sensitive attachment is routed to the review queue.
        rq = conn.execute(
            "SELECT category FROM email_review_queue WHERE message_id='m1' AND category='contracts'"
        ).fetchone()
        assert rq is not None
    finally:
        conn.close()


def test_body_preview_drive_link_creates_candidate() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    msg = _msg("m1")
    msg["bodyPreview"] = (
        "latest set at https://hbcc.sharepoint.com/sites/tropical/Shared%20Documents/x.pdf"
    )
    reader = FakeReader(by_folder={"AAMkInbox": [msg]})
    result = EmailMessageIndexer(reader, store).index(project_key="tropical", lookback_days=30)
    assert result.source_link_candidates >= 1
    conn = sqlite3.connect(db)
    try:
        cand = conn.execute(
            "SELECT candidate_type FROM email_relationship_candidates "
            "WHERE message_id='m1' AND match_signal='sharepoint_link_in_body_preview'"
        ).fetchone()
        assert cand is not None and cand[0] == "sharepoint_drive_item"
    finally:
        conn.close()


def test_attachment_enrichment_is_idempotent() -> None:
    db = _tmp_db()
    store = _store_with_inbox(db)
    reader = FakeReader(
        by_folder={"AAMkInbox": [_msg("m1", has_attachments=True)]},
        attachments={
            "m1": [
                {
                    "id": "a1",
                    "name": "Change Order 3.pdf",
                    "contentType": "application/pdf",
                    "size": 5,
                }
            ]
        },
    )
    indexer = EmailMessageIndexer(reader, store)
    indexer.index(project_key="tropical", lookback_days=30)
    first = _enrich_counts(db)
    indexer.index(project_key="tropical", lookback_days=30)
    second = _enrich_counts(db)
    assert second == first  # attachments, candidates, review-queue rows all stable
