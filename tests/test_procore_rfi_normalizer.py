"""Phase 04 Prompt 04 — RFI canonical normalization (pure-function unit tests)."""

from __future__ import annotations

import json

from hb_assistant.construction.fixtures.procore import RFI_SAMPLE_PAYLOAD
from hb_assistant.procore.normalizers.rfi import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_rfi,
    normalize_rfi_payload_block,
    normalize_rfi_reply,
)

_FETCHED_AT = "2026-05-28T00:00:00+00:00"
_CORRELATION = "synthetic-corr-001"


def test_normalize_rfi_carries_canonical_keys_and_metadata() -> None:
    raw = RFI_SAMPLE_PAYLOAD[0]
    record = normalize_rfi(
        raw,
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["source_project_key"] == "tropical"
    assert record["endpoint_id"] == "list-rfis"
    assert record["category"] == "rfis"
    assert record["entity_stable_key"] == raw["id"]
    assert record["correlation_id"] == _CORRELATION
    assert record["redaction_applied"] is True
    assert record["normalization_schema_version"] == NORMALIZATION_SCHEMA_VERSION
    fields = record["canonical_fields"]
    assert fields["number"] == raw["number"]
    assert fields["subject"] == raw["subject"]
    assert fields["status"] == raw["status"]
    assert fields["source_url"] == raw["html_url"]
    # Body never carried through
    assert "body" not in fields
    assert "description" not in fields


def test_normalize_rfi_review_flag_low_risk_default() -> None:
    raw = RFI_SAMPLE_PAYLOAD[0]  # benign status + present assignee
    record = normalize_rfi(
        raw,
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is False
    assert record["routing_reason"] == "default_low_risk"


def test_normalize_rfi_review_flag_legal_status() -> None:
    raw = RFI_SAMPLE_PAYLOAD[
        2
    ]  # status: legal_review_required + change order subject + no assignee
    record = normalize_rfi(
        raw,
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    # Status fragment wins before subject/assignee fragments
    assert record["routing_reason"].startswith("status_contains:")


def test_normalize_rfi_source_url_synthesized_from_html_url() -> None:
    record = normalize_rfi(
        {"id": "x1", "html_url": "https://example.com/rfis/x1"},
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["canonical_fields"]["source_url"] == "https://example.com/rfis/x1"


def test_normalize_rfi_omits_source_url_when_absent() -> None:
    record = normalize_rfi(
        {"id": "x2"},
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert "source_url" not in record["canonical_fields"]


def test_normalize_rfi_reply_always_review_required() -> None:
    raw_reply = RFI_SAMPLE_PAYLOAD[0]["replies"][0]
    record = normalize_rfi_reply(
        raw_reply,
        parent_procore_id="synthetic-rfi-001",
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "rfi_reply_default_review_required"
    assert record["category"] == "rfi_replies"
    assert record["parent_rfi_stable_key"] == "synthetic-rfi-001"
    assert record["entity_stable_key"].startswith("reply-synthetic-rfi-001-")
    # Body reduced to structural summary — never carried as-is.
    serialized = json.dumps(record)
    assert raw_reply["body"] not in serialized


def test_normalize_rfi_payload_block_yields_parent_and_reply_counts() -> None:
    rfis, replies = normalize_rfi_payload_block(
        RFI_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert len(rfis) == 3
    assert len(replies) == 5
    # Reply parent linkage covers each fixture RFI that has nested replies.
    parents = {r["parent_rfi_stable_key"] for r in replies}
    assert parents == {"synthetic-rfi-001", "synthetic-rfi-002", "synthetic-rfi-003"}


def test_normalize_rfi_payload_block_never_serializes_body_text() -> None:
    rfis, replies = normalize_rfi_payload_block(
        RFI_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-rfis",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    serialized = json.dumps({"rfis": rfis, "replies": replies})
    for raw in RFI_SAMPLE_PAYLOAD:
        for raw_reply in raw["replies"]:
            assert raw_reply["body"] not in serialized
