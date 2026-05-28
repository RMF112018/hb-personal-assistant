"""Phase 04 Prompt 05 — Submittal canonical normalization (pure-function unit tests)."""

from __future__ import annotations

import json

from hb_assistant.construction.fixtures.procore import SUBMITTAL_SAMPLE_PAYLOAD
from hb_assistant.procore.normalizers.submittal import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_submittal,
    normalize_submittal_package,
    normalize_submittal_payload_block,
    normalize_submittal_response,
)

_FETCHED_AT = "2026-05-28T00:00:00+00:00"
_CORRELATION = "synthetic-corr-002"


def test_normalize_submittal_carries_canonical_keys_and_metadata() -> None:
    raw = SUBMITTAL_SAMPLE_PAYLOAD[0]
    record = normalize_submittal(
        raw,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["source_project_key"] == "tropical"
    assert record["endpoint_id"] == "list-submittals"
    assert record["category"] == "submittals"
    assert record["entity_stable_key"] == raw["id"]
    assert record["correlation_id"] == _CORRELATION
    assert record["redaction_applied"] is True
    assert record["normalization_schema_version"] == NORMALIZATION_SCHEMA_VERSION
    fields = record["canonical_fields"]
    assert fields["number"] == raw["number"]
    assert fields["title"] == raw["title"]
    assert fields["status"] == raw["status"]
    assert fields["type"] == raw["type"]
    assert fields["specification_section"] == raw["specification_section"]
    assert fields["source_url"] == raw["html_url"]


def test_normalize_submittal_review_flag_low_risk_default() -> None:
    raw = SUBMITTAL_SAMPLE_PAYLOAD[0]
    record = normalize_submittal(
        raw,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is False
    assert record["routing_reason"] == "default_low_risk"


def test_normalize_submittal_review_flag_revise_and_resubmit_status() -> None:
    raw = SUBMITTAL_SAMPLE_PAYLOAD[2]  # status: revise_and_resubmit, contract amendment subject, no assignee
    record = normalize_submittal(
        raw,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    # Status fragment fires before subject + assignee fragments
    assert record["routing_reason"].startswith("status_contains:")


def test_normalize_submittal_review_flag_assignee_missing() -> None:
    record = normalize_submittal(
        {"id": "x1", "status": "open", "title": "Generic submittal"},
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "assignee_missing"


def test_normalize_submittal_source_url_synthesized_from_html_url() -> None:
    record = normalize_submittal(
        {
            "id": "x2",
            "html_url": "https://example.com/submittals/x2",
            "assignee_id": "u1",
        },
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["canonical_fields"]["source_url"] == "https://example.com/submittals/x2"


def test_normalize_submittal_response_always_review_required() -> None:
    raw_response = SUBMITTAL_SAMPLE_PAYLOAD[0]["responses"][0]
    record = normalize_submittal_response(
        raw_response,
        parent_procore_id="synthetic-sub-001",
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "submittal_response_default_review_required"
    assert record["category"] == "submittal_responses"
    assert record["parent_submittal_stable_key"] == "synthetic-sub-001"
    assert record["entity_stable_key"].startswith("response-synthetic-sub-001-")
    # Comment body reduced to hash-only summary — never the text itself.
    serialized = json.dumps(record)
    assert raw_response["comment"] not in serialized


def test_normalize_submittal_package_always_review_required() -> None:
    raw_package = SUBMITTAL_SAMPLE_PAYLOAD[0]["packages"][0]
    record = normalize_submittal_package(
        raw_package,
        parent_procore_id="synthetic-sub-001",
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "submittal_package_default_review_required"
    assert record["category"] == "submittal_packages"
    assert record["entity_stable_key"].startswith("package-synthetic-sub-001-")
    fields = record["canonical_fields"]
    assert fields["number"] == raw_package["number"]
    assert fields["title"] == raw_package["title"]


def test_normalize_submittal_payload_block_yields_three_lists() -> None:
    submittals, responses, packages = normalize_submittal_payload_block(
        SUBMITTAL_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert len(submittals) == 3
    assert len(responses) == 4
    assert len(packages) == 2
    response_parents = {r["parent_submittal_stable_key"] for r in responses}
    package_parents = {p["parent_submittal_stable_key"] for p in packages}
    assert response_parents == {
        "synthetic-sub-001",
        "synthetic-sub-002",
        "synthetic-sub-003",
    }
    assert package_parents == {"synthetic-sub-001", "synthetic-sub-003"}


def test_normalize_submittal_payload_block_never_serializes_body_text() -> None:
    submittals, responses, packages = normalize_submittal_payload_block(
        SUBMITTAL_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    serialized = json.dumps(
        {"submittals": submittals, "responses": responses, "packages": packages}
    )
    for raw in SUBMITTAL_SAMPLE_PAYLOAD:
        for raw_response in raw["responses"]:
            assert raw_response["comment"] not in serialized
        for raw_package in raw["packages"]:
            description = raw_package.get("description")
            if description:
                assert description not in serialized
