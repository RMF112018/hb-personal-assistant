"""Unit tests for calendar/contact live payload mapping."""

from __future__ import annotations

from hb_assistant.apple_mcc.ops.capture_run import _calendar_payload, _contact_payload


def test_calendar_payload_identity() -> None:
    item = {
        "event_id": "ek-1",
        "calendar_id": "cal-1",
        "source_title": "iCloud",
        "calendar_title": "Personal",
        "summary": "Standup",
        "notes": "notes",
        "location": "HQ",
        "start": "2026-07-30T13:00:00Z",
        "end": "2026-07-30T14:00:00Z",
        "all_day": False,
        "has_recurrence": False,
        "url": "",
    }
    p = _calendar_payload(item, capture_run_id="cap1")
    assert p["domain"] == "calendar"
    assert p["provider"] == "apple_eventkit"
    assert len(p["occurrence_key"]) == 64
    assert len(p["revision_key"]) == 64
    assert p["source_quality"] == "apple_eventkit_full"


def test_contact_payload_identity() -> None:
    item = {
        "cn_id": "CN-1",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "organization": "",
        "contact_type": "person",
        "container": "On My Mac",
        "emails": [{"label": "work", "value": "ada@example.com"}],
        "phones": [],
    }
    p = _contact_payload(item, capture_run_id="cap1")
    assert p["domain"] == "contacts"
    assert p["provider"] == "cncontact_local"
    assert len(p["contact_entity_id"]) == 64
    assert "ada@example.com" in p["structured_payload_json"]
