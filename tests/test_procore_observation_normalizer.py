"""Phase 04 Prompt 06 — Observation canonical normalization tests."""

from __future__ import annotations

import json

from hb_assistant.construction.fixtures.procore import OBSERVATION_SAMPLE_PAYLOAD
from hb_assistant.procore.normalizers.observation import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_observation,
    normalize_observation_comment,
    normalize_observation_payload_block,
)

_FETCHED_AT = "2026-05-28T00:00:00+00:00"
_CORRELATION = "synthetic-corr-003"


def test_normalize_observation_carries_canonical_keys_and_metadata() -> None:
    raw = OBSERVATION_SAMPLE_PAYLOAD[0]
    record = normalize_observation(
        raw,
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["source_project_key"] == "tropical"
    assert record["endpoint_id"] == "list-observations"
    assert record["category"] == "observations"
    assert record["entity_stable_key"] == raw["id"]
    assert record["correlation_id"] == _CORRELATION
    assert record["redaction_applied"] is True
    assert record["normalization_schema_version"] == NORMALIZATION_SCHEMA_VERSION
    fields = record["canonical_fields"]
    assert fields["number"] == raw["number"]
    assert fields["title"] == raw["title"]
    assert fields["type"] == raw["type"]
    assert fields["severity"] == raw["severity"]
    assert fields["source_url"] == raw["html_url"]
    # Description is never carried — only a hash summary.
    assert "description" not in fields
    assert "body" not in fields
    assert record["description_summary"]["type"] == "string"
    assert "hash_prefix" in record["description_summary"]


def test_normalize_observation_low_risk_default() -> None:
    record = normalize_observation(
        OBSERVATION_SAMPLE_PAYLOAD[0],
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is False
    assert record["routing_reason"] == "default_low_risk"
    assert record["safety_route"] is False


def test_normalize_observation_status_fragment_near_miss() -> None:
    # type=near-miss → status-fragment hit at the "type" field; safety route on.
    record = normalize_observation(
        OBSERVATION_SAMPLE_PAYLOAD[1],
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"].startswith("type_contains:")
    assert record["safety_route"] is True


def test_normalize_observation_body_fragment_injury() -> None:
    # Observation 3: status=open, subtype=injury fires status-fragment scan first
    # at the "subtype" field; safety route on.
    record = normalize_observation(
        OBSERVATION_SAMPLE_PAYLOAD[2],
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["safety_route"] is True
    # subtype scan precedes body scan; either is acceptable safety origin.
    assert (
        record["routing_reason"].startswith("subtype_contains:")
        or record["routing_reason"].startswith("body_contains:")
        or record["routing_reason"].startswith("type_contains:")
    )


def test_normalize_observation_body_only_safety_trigger() -> None:
    # Construct a payload with bland status/type/title but a safety keyword
    # buried in the description.
    raw = {
        "id": "x9",
        "status": "open",
        "type": "general",
        "title": "Routine walk",
        "assignee_id": "u1",
        "description": "Reviewing corrective action items from last week.",
    }
    record = normalize_observation(
        raw,
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"].startswith("body_contains:")
    assert record["safety_route"] is True


def test_normalize_observation_assignee_missing_only_when_no_safety_signal() -> None:
    raw = {
        "id": "x10",
        "status": "open",
        "type": "general",
        "title": "Routine walk",
        "description": "Nothing of note.",
    }
    record = normalize_observation(
        raw,
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "assignee_missing"
    assert record["safety_route"] is False


def test_normalize_observation_source_url_synthesized_from_html_url() -> None:
    record = normalize_observation(
        {
            "id": "x2",
            "status": "open",
            "html_url": "https://example.com/observations/x2",
            "assignee_id": "u1",
        },
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["canonical_fields"]["source_url"] == "https://example.com/observations/x2"


def test_normalize_observation_comment_always_review_required() -> None:
    raw_comment = OBSERVATION_SAMPLE_PAYLOAD[0]["comments"][0]
    record = normalize_observation_comment(
        raw_comment,
        parent_observation_stable_key="synthetic-obs-001",
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "observation_comment_default_review_required"
    assert record["category"] == "observation_comments"
    assert record["entity_stable_key"].startswith("comment-synthetic-obs-001-")
    serialized = json.dumps(record)
    assert raw_comment["body"] not in serialized


def test_normalize_observation_payload_block_yields_two_lists() -> None:
    observations, comments = normalize_observation_payload_block(
        OBSERVATION_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert len(observations) == 3
    assert len(comments) == 3
    parents = {c["parent_observation_stable_key"] for c in comments}
    assert parents == {
        "synthetic-obs-001",
        "synthetic-obs-002",
        "synthetic-obs-003",
    }
    # Safety routing: observations 2 and 3 fire; observation 1 does not.
    safety_routed = [o for o in observations if o["safety_route"]]
    assert len(safety_routed) == 2


def test_normalize_observation_payload_block_never_serializes_body_text() -> None:
    observations, comments = normalize_observation_payload_block(
        OBSERVATION_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-observations",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    serialized = json.dumps({"observations": observations, "comments": comments})
    for raw in OBSERVATION_SAMPLE_PAYLOAD:
        # Descriptions are never persisted as raw text.
        assert raw["description"] not in serialized
        for raw_comment in raw["comments"]:
            assert raw_comment["body"] not in serialized
