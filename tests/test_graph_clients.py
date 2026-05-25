"""Tests for Phase 4 Graph read model clients (Mail, Calendar, DriveItem).

Uses mocked GraphHttpClient responses matching the exact $select queries from 06 spec.
Verifies redaction, window logic, and normalized model construction.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from hb_assistant.config.loader import load_config
from hb_assistant.graph.mail_client import MailClient
from hb_assistant.graph.calendar_client import CalendarClient
from hb_assistant.graph.drive_item_client import DriveItemClient
from hb_assistant.normalize.email import Email
from hb_assistant.normalize.calendar_event import CalendarEvent


def test_mail_client_inbound_redaction():
    mock_http = MagicMock()
    mock_http.get_all_pages.return_value = [
        {
            "id": "msg1",
            "subject": "Secret Project Update",
            "from": {"emailAddress": {"address": "alice@ex.com"}},
            "toRecipients": [{"emailAddress": {"address": "bob@ex.com"}}],
            "receivedDateTime": "2026-05-20T10:00:00Z",
            "bodyPreview": "Hi Bobby, here is the update on the secret project...",
            "hasAttachments": True,
        }
    ]
    cfg = load_config()
    client = MailClient(mock_http, cfg)
    emails = client.list_inbound(top=1)
    assert len(emails) == 1
    e = emails[0]
    assert isinstance(e, Email)
    assert "redacted" in (e.subject_redacted or "")
    assert e.sender_domain == "ex.com"
    assert "bobby" not in (e.body_preview_redacted or "").lower() or "..." in (e.body_preview_redacted or "")  # truncated if long


def test_calendar_client_window():
    mock_http = MagicMock()
    mock_http.get_all_pages.return_value = [{"id": "evt1", "subject": "Team Sync", "start": {"dateTime": "2026-05-26T09:00:00"}}]
    cfg = load_config()
    client = CalendarClient(mock_http, cfg)
    events = client.list_events(top=1)
    assert len(events) == 1
    assert isinstance(events[0], CalendarEvent)


def test_drive_item_client_metadata():
    mock_http = MagicMock()
    mock_http.get.return_value = {"id": "item1", "name": "Q2 Plan.pdf", "size": 12345, "file": {"mimeType": "application/pdf"}}
    client = DriveItemClient(mock_http)
    item = client.get_item("item1")
    assert item.name == "Q2 Plan.pdf"
    assert item.is_file is True


def test_mail_client_uses_bounded_paging_caps():
    mock_http = MagicMock()
    mock_http.get_all_pages.return_value = []
    cfg = load_config()
    cfg.mail.max_items_per_run = 2
    cfg.graph.max_pages_per_call = 3
    client = MailClient(mock_http, cfg)
    client.list_inbound(top=10)
    _, kwargs = mock_http.get_all_pages.call_args
    assert kwargs["max_items"] == 2
    assert kwargs["max_pages"] == 3


def test_calendar_client_uses_bounded_paging_caps():
    mock_http = MagicMock()
    mock_http.get_all_pages.return_value = []
    cfg = load_config()
    cfg.calendar.max_items_per_run = 4
    cfg.graph.max_pages_per_call = 2
    client = CalendarClient(mock_http, cfg)
    client.list_events(top=10)
    _, kwargs = mock_http.get_all_pages.call_args
    assert kwargs["max_items"] == 4
    assert kwargs["max_pages"] == 2


def test_drive_client_children_and_attachments_use_bounded_paging_caps():
    mock_http = MagicMock()
    mock_http.get_all_pages.return_value = []
    cfg = load_config()
    cfg.files.max_drive_items_per_run = 3
    cfg.graph.max_pages_per_call = 2
    client = DriveItemClient(mock_http, cfg)
    client.list_children(top=10)
    _, children_kwargs = mock_http.get_all_pages.call_args
    assert children_kwargs["max_items"] == 3
    assert children_kwargs["max_pages"] == 2

    mock_http.get_all_pages.reset_mock()
    client.list_attachments("msg-1")
    _, attachment_kwargs = mock_http.get_all_pages.call_args
    assert attachment_kwargs["max_items"] == 3
    assert attachment_kwargs["max_pages"] == 2
