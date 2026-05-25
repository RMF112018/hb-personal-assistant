"""Normalized Email model (inbound/sent) with redaction and source links.

Matches 06 spec minimal fields + sqlite emails table expectations.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .redaction import redact_recipient, redact_subject, truncate_preview


class Email(BaseModel):
    """Redacted, source-linked representation of a Graph message (mail)."""

    # Core identifiers (immutable where possible)
    id: str
    immutable_id: Optional[str] = None
    conversation_id: Optional[str] = None
    internet_message_id: Optional[str] = None
    web_link: Optional[str] = None

    # Folder context
    folder: str  # "inbox", "sent", etc.

    # Redacted/timestamped fields
    subject_redacted: Optional[str] = None
    sender_domain: Optional[str] = None
    sender_hash: Optional[str] = None
    from_redacted: Optional[str] = None
    to_recipients_redacted: List[str] = Field(default_factory=list)
    cc_recipients_redacted: List[str] = Field(default_factory=list)
    received_datetime: Optional[datetime] = None
    sent_datetime: Optional[datetime] = None

    # Preview (bounded, redacted)
    body_preview_redacted: Optional[str] = None

    # Flags
    has_attachments: bool = False
    importance: Optional[str] = None

    # Body classification flags (Phase 6) — persisted in emails table, default False/0 in DB
    body_checked: bool = False
    body_mention_detected: bool = False

    # Source traceability (populated by client or registry)
    source_record_id: Optional[int] = None
    source_links: List[dict] = Field(default_factory=list)  # type from source-link-types.json

    @classmethod
    def from_graph_message(cls, msg: dict, folder: str = "inbox") -> "Email":
        """Construct from raw Graph message dict (after $select), applying redaction."""
        from_addr = msg.get("from", {}).get("emailAddress", {})
        sender = from_addr.get("address")

        return cls(
            id=msg.get("id"),
            immutable_id=msg.get("internetMessageId"),  # or use Prefer header result if available
            conversation_id=msg.get("conversationId"),
            internet_message_id=msg.get("internetMessageId"),
            web_link=msg.get("webLink"),
            folder=folder,
            subject_redacted=redact_subject(msg.get("subject")),
            sender_domain=sender.split("@")[-1] if sender else None,
            sender_hash=sender.split("@")[0] if sender else None,
            from_redacted=redact_recipient(sender),
            to_recipients_redacted=[redact_recipient(r.get("emailAddress", {}).get("address")) for r in msg.get("toRecipients", []) if r.get("emailAddress")],
            cc_recipients_redacted=[redact_recipient(r.get("emailAddress", {}).get("address")) for r in msg.get("ccRecipients", []) if r.get("emailAddress")],
            received_datetime=msg.get("receivedDateTime"),
            sent_datetime=msg.get("sentDateTime"),
            body_preview_redacted=truncate_preview(msg.get("bodyPreview")),
            has_attachments=msg.get("hasAttachments", False),
            importance=msg.get("importance"),
            body_checked=False,
            body_mention_detected=False,
        )
