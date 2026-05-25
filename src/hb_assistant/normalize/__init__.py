"""Normalized, redacted, source-linked models for Graph mail/calendar/attachments/files.

These are the canonical objects produced by the Phase 4 clients.
They match the shape expected by the local data model (07) and source link registry.
All PII fields are redacted/hashed per 06 spec; no full bodies or file contents are stored here.
"""

from .email import Email
from .calendar_event import CalendarEvent
from .attachment import Attachment
from .drive_item import DriveItem
from .redaction import redact_subject, redact_recipient, hash_value, truncate_preview

__all__ = [
    "Email",
    "CalendarEvent",
    "Attachment",
    "DriveItem",
    "redact_subject",
    "redact_recipient",
    "hash_value",
    "truncate_preview",
]
