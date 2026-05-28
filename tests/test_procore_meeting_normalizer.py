"""Phase 04 Prompt 07 — Meeting + meeting-topic canonical normalization tests."""

from __future__ import annotations

import json

from hb_assistant.construction.fixtures.procore import (
    MEETING_SAMPLE_PAYLOAD,
    MEETING_TOPIC_SAMPLE_PAYLOAD,
)
from hb_assistant.procore.normalizers.meeting import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_meeting,
    normalize_meeting_payload_block,
    normalize_meeting_topic,
    normalize_meeting_topic_payload_block,
)

_FETCHED_AT = "2026-05-28T00:00:00+00:00"
_CORRELATION = "synthetic-corr-004"


def test_normalize_meeting_carries_canonical_keys_and_metadata() -> None:
    raw = MEETING_SAMPLE_PAYLOAD[0]
    record = normalize_meeting(
        raw,
        project_key="tropical",
        endpoint_id="list-meetings",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["source_project_key"] == "tropical"
    assert record["endpoint_id"] == "list-meetings"
    assert record["category"] == "meetings"
    assert record["entity_stable_key"] == raw["id"]
    assert record["correlation_id"] == _CORRELATION
    assert record["redaction_applied"] is True
    assert record["normalization_schema_version"] == NORMALIZATION_SCHEMA_VERSION
    fields = record["canonical_fields"]
    assert fields["number"] == raw["number"]
    assert fields["title"] == raw["title"]
    assert fields["start_time"] == raw["start_time"]
    assert fields["source_url"] == raw["html_url"]
    # Parent meetings carry no description summary by design.
    assert "description_summary" not in record


def test_normalize_meeting_low_risk_default() -> None:
    record = normalize_meeting(
        MEETING_SAMPLE_PAYLOAD[0],
        project_key="tropical",
        endpoint_id="list-meetings",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is False
    assert record["routing_reason"] == "default_low_risk"


def test_normalize_meeting_subject_fragment_change_order() -> None:
    record = normalize_meeting(
        MEETING_SAMPLE_PAYLOAD[1],
        project_key="tropical",
        endpoint_id="list-meetings",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"].startswith("subject_contains:")


def test_normalize_meeting_status_fragment_legal_hold() -> None:
    record = normalize_meeting(
        MEETING_SAMPLE_PAYLOAD[2],
        project_key="tropical",
        endpoint_id="list-meetings",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"].startswith("status_contains:")


def test_normalize_meeting_source_url_synthesized_from_html_url() -> None:
    record = normalize_meeting(
        {"id": "m9", "html_url": "https://example.com/meetings/m9"},
        project_key="tropical",
        endpoint_id="list-meetings",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["canonical_fields"]["source_url"] == "https://example.com/meetings/m9"


def test_normalize_meeting_topic_carries_canonical_keys_and_hash_summaries() -> None:
    raw = MEETING_TOPIC_SAMPLE_PAYLOAD[0]
    record = normalize_meeting_topic(
        raw,
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["category"] == "meeting_topics"
    assert record["entity_stable_key"] == raw["id"]
    fields = record["canonical_fields"]
    assert fields["title"] == raw["title"]
    assert fields["parent_meeting_id"] == raw["parent_meeting_id"]
    assert fields["source_url"] == raw["html_url"]
    # Body text never carried — only hash summaries.
    assert "description" not in fields
    assert "action_items" not in fields
    assert record["description_summary"]["type"] == "string"
    assert record["action_items_summary"]["type"] == "string"


def test_normalize_meeting_topic_low_risk_default() -> None:
    record = normalize_meeting_topic(
        MEETING_TOPIC_SAMPLE_PAYLOAD[0],
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is False
    assert record["routing_reason"] == "default_low_risk"
    assert record["safety_route"] is False


def test_normalize_meeting_topic_body_safety_injury() -> None:
    # Topic #2 description carries "injury" — body-fragment safety trigger.
    record = normalize_meeting_topic(
        MEETING_TOPIC_SAMPLE_PAYLOAD[1],
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["safety_route"] is True
    # Description carries "injury" but also "safety" in title — title is scanned
    # before body, so subject_contains:safety wins.
    assert (
        record["routing_reason"].startswith("body_contains:")
        or record["routing_reason"].startswith("subject_contains:")
    )


def test_normalize_meeting_topic_claim_is_review_but_not_safety() -> None:
    # Topic #3 has "claim" in title — generic review fragment, NOT safety.
    record = normalize_meeting_topic(
        MEETING_TOPIC_SAMPLE_PAYLOAD[2],
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["safety_route"] is False
    assert record["routing_reason"].startswith("subject_contains:claim") or \
           record["routing_reason"].startswith("status_contains:claim")


def test_normalize_meeting_topic_action_items_list_hashed() -> None:
    # Topic #2's action_items is a list of two strings — should be flattened and hashed.
    record = normalize_meeting_topic(
        MEETING_TOPIC_SAMPLE_PAYLOAD[1],
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    summary = record["action_items_summary"]
    assert summary["type"] == "string"
    assert summary["length"] > 0
    serialized = json.dumps(record)
    for item in MEETING_TOPIC_SAMPLE_PAYLOAD[1]["action_items"]:
        assert item not in serialized


def test_normalize_meeting_topic_assignee_missing_when_no_safety_signal() -> None:
    record = normalize_meeting_topic(
        {"id": "t9", "status": "open", "title": "Pure metadata", "description": "Routine"},
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "assignee_missing"
    assert record["safety_route"] is False


def test_meeting_payload_block_yields_meeting_one_tuple() -> None:
    (meetings,) = normalize_meeting_payload_block(
        MEETING_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-meetings",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert len(meetings) == 3


def test_meeting_topic_payload_block_yields_topic_one_tuple() -> None:
    (topics,) = normalize_meeting_topic_payload_block(
        MEETING_TOPIC_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert len(topics) == 4
    safety_routed = [t for t in topics if t["safety_route"]]
    # Only topic #2 (safety description) should route safety; topic #3 (claim
    # in title) is generic review, not safety.
    assert len(safety_routed) == 1


def test_meeting_topic_payload_block_never_serializes_body_text() -> None:
    (topics,) = normalize_meeting_topic_payload_block(
        MEETING_TOPIC_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-meeting-topics",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    serialized = json.dumps(topics)
    for raw in MEETING_TOPIC_SAMPLE_PAYLOAD:
        description = raw.get("description")
        if description:
            assert description not in serialized
        action_items = raw.get("action_items")
        if isinstance(action_items, str):
            assert action_items not in serialized
        elif isinstance(action_items, list):
            for item in action_items:
                assert item not in serialized


# ----------------------------------------------------------------------------
# Phase 04A backlog: v1.1 payload shape support
# ----------------------------------------------------------------------------


_V11_MEETING_RAW = {
    "id": 901,
    "title": "OAC weekly coordination",
    "starts_at": "2026-06-01T15:00:00Z",
    "ends_at": "2026-06-01T16:00:00Z",
    "location": "Trailer B",
    "created_by_id": 4242,
    "meeting_topics_count": 7,
    "created_at": "2026-05-20T00:00:00Z",
    "updated_at": "2026-05-31T00:00:00Z",
    # v1.1 fields that the normalizer intentionally omits from canonical
    # storage to preserve the metadata-only contract:
    "description": "OAC meeting body that must never appear in canonical storage.",
    "is_private": False,
    "mode": "in_person",
}


def test_normalize_meeting_accepts_v1_1_shape_and_carries_v1_1_keys() -> None:
    record = normalize_meeting(
        _V11_MEETING_RAW,
        project_key="tropical",
        endpoint_id="meetings",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    canonical = record["canonical_fields"]
    # v1.1 keys present
    assert canonical.get("starts_at") == "2026-06-01T15:00:00Z"
    assert canonical.get("ends_at") == "2026-06-01T16:00:00Z"
    assert canonical.get("created_by_id") == 4242
    assert canonical.get("meeting_topics_count") == 7
    assert canonical.get("title") == "OAC weekly coordination"
    assert canonical.get("location") == "Trailer B"
    # v1.0 keys absent from this payload should not appear in canonical
    assert "start_time" not in canonical
    assert "end_time" not in canonical
    assert "organizer_id" not in canonical
    # Metadata-only contract: description must NOT be carried even if present
    assert "description" not in canonical
    description_text = _V11_MEETING_RAW["description"]
    assert isinstance(description_text, str)
    assert description_text not in json.dumps(record)


# ----------------------------------------------------------------------------
# meeting-detail: rich per-meeting payload with PII + nested topics
# ----------------------------------------------------------------------------


from hb_assistant.procore.normalizers.meeting import (  # noqa: E402
    extract_topics_from_categories,
    normalize_meeting_detail,
)

_DETAIL_RAW = {
    "id": 82593,
    "meeting_template_id": 82593,
    "position": 1,
    "created_by_id": 1,
    "title": "Jon's Meeting",
    "location": "Victoria Conference Room",
    "occurred": False,
    "starts_at": "2021-07-23T10:00:00Z",
    "ends_at": "2021-07-23T17:00:00Z",
    "time_zone": "US/Pacific",
    "is_private": False,
    "is_draft": False,
    "mode": "minutes",
    "created_at": "2021-07-23T10:00:00Z",
    "updated_at": "2021-07-23T10:00:00Z",
    "description": "PII-free description text",
    "conclusion": "PII-free conclusion text",
    "remote_meeting_url": "https://zoom.us/j/123456789?pwd=SECRET_TOKEN_DO_NOT_LEAK",
    "attachments": [{"id": 5324, "url": "http://www.example.com/", "filename": "x.jpg"}],
    "attendees": [
        {
            "id": 972145,
            "status": "Absent",
            "login_information": {
                "id": 160586,
                "login": "carl.contractor@example.com",
                "name": "Carl Contractor",
            },
        },
        {
            "id": 972146,
            "status": "Present",
            "login_information": {
                "id": 160587,
                "login": "alice.architect@example.com",
                "name": "Alice Architect",
            },
        },
    ],
    "meeting_categories": [
        {
            "id": 192424,
            "title": "Uncategorized Items",
            "position": 0,
            "meeting_topic": [
                {
                    "id": 965039,
                    "number": "1.1",
                    "title": "34' Level",
                    "minutes": "<p>HTML content with sensitive details</p>",
                    "description": "Need pricing from vendor",
                    "status": "On Hold",
                    "priority": "Low",
                    "assignments": [
                        {
                            "id": 160586,
                            "login": "carl.contractor@example.com",
                            "name": "Carl Contractor",
                        }
                    ],
                }
            ],
        }
    ],
}


def test_normalize_meeting_detail_carries_rich_schema_and_redacts_pii() -> None:
    record = normalize_meeting_detail(
        _DETAIL_RAW,
        project_key="tropical",
        endpoint_id="meeting-detail",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    canonical = record["canonical_fields"]
    serialized = json.dumps(record)

    # Structured fields preserved
    assert canonical["id"] == 82593
    assert canonical["title"] == "Jon's Meeting"
    assert canonical["time_zone"] == "US/Pacific"
    assert canonical["mode"] == "minutes"
    assert canonical["is_private"] is False

    # Free-text reduced to hash-only summaries
    assert "description_summary" in canonical
    assert "conclusion_summary" in canonical
    assert canonical["description_summary"]["hash_prefix"]
    description_text = _DETAIL_RAW["description"]
    conclusion_text = _DETAIL_RAW["conclusion"]
    assert isinstance(description_text, str)
    assert isinstance(conclusion_text, str)
    assert description_text not in serialized
    assert conclusion_text not in serialized

    # remote_meeting_url: path-only, query stripped
    assert canonical["remote_meeting_url_redacted"] == "https://zoom.us/j/123456789"
    assert "SECRET_TOKEN_DO_NOT_LEAK" not in serialized
    assert "?" not in canonical["remote_meeting_url_redacted"]

    # Attendees: counts + hashed identifiers, NO email/name strings
    attendees = canonical["attendees_summary"]
    assert attendees["count"] == 2
    assert len(attendees["hashed_identifiers"]) == 2
    for a in attendees["hashed_identifiers"]:
        assert "hash_prefix" in a
        assert len(a["hash_prefix"]) == 12
        assert "status" in a
    assert "carl.contractor@example.com" not in serialized
    assert "alice.architect@example.com" not in serialized
    assert "Carl Contractor" not in serialized
    assert "Alice Architect" not in serialized

    # Structural counts
    assert canonical["meeting_categories_count"] == 1
    assert canonical["attachments_count"] == 1
    assert canonical["category_titles"] == ["Uncategorized Items"]

    # Review-required because PII bearing
    assert record["review_required"] is True


def test_normalize_meeting_detail_extracts_nested_topics_from_categories() -> None:
    topics = extract_topics_from_categories(_DETAIL_RAW)
    assert len(topics) == 1
    assert topics[0]["id"] == 965039
    assert topics[0]["title"] == "34' Level"
