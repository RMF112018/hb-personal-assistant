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
