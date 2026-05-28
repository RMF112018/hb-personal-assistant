"""Phase 04A punch-items normalizer tests — PII hashing + free-text hashing +
custom_fields structured/hashed treatment."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.punch_item import normalize_punch_item

_CORRELATION = "synthetic-corr-punch"
_FETCHED_AT = "2026-05-28T00:00:00+00:00"


_PUNCH_RAW = {
    "id": 83978,
    "name": "Test punch item",
    "reference": "3A",
    "position": 1,
    "priority": "High",
    "private": False,
    "status": "Open",
    "workflow_status": "initiated",
    "due_date": "2026-09-30",
    "created_at": "2026-05-23T21:39:40Z",
    "updated_at": "2026-05-24T21:39:40Z",
    "closed_at": None,
    "has_resolved_responses": True,
    "has_unresolved_responses": True,
    "cost_impact": "yes_known",
    "cost_impact_amount": "100.0",
    "schedule_impact": "yes_known",
    "schedule_impact_days": 3,
    "schedule_risk": "ml_high",
    "schedule_risk_confidence": 90,
    "schedule_risk_probability": 90,
    # Free-text bodies that must be hashed.
    "description": "Detailed description that must not appear in canonical storage.",
    "schedule_risk_reason": "Risk reasoning that must not appear in canonical storage.",
    # Short-label structured nested objects.
    "location": {
        "id": 15504,
        "name": "North Building>First Floor>Electrical Closet",
        "code": "L1",
        "parent_id": 788866,
    },
    "trade": {"id": 999, "name": "09 - acoustical panels", "active": True},
    "punch_item_type": {"id": 44165, "name": "Extra Work"},
    "cost_code": {"id": 12345, "name": "Earthwork"},
    # PII-bearing people refs.
    "ball_in_court": [
        {"id": 1738090, "name": "John Doe", "locale": "ko"},
    ],
    "created_by": {"id": 1738090, "name": "John Doe", "locale": "ko", "company_name": "Brickworks"},
    "closed_by": None,
    "punch_item_manager": {"id": 1738091, "name": "Jane Manager", "company_name": "Brickworks"},
    "final_approver": {"id": 1738092, "name": "Alex Approver", "company_name": "Brickworks"},
    "assignees": [
        {"id": 160586, "login": "carl.contractor@example.com", "name": "Carl Contractor"},
    ],
    "assignments": [
        {
            "id": 333675,
            "approved": True,
            "comment": "Body comment must not appear in canonical storage.",
            "login_information_id": 420,
            "login_information_name": "Edgar Admin",
            "login_information": {
                "id": 160586,
                "login": "carl.contractor@example.com",
                "name": "Carl Contractor",
            },
            "attachments": [{"id": 5324, "url": "http://www.example.com/", "filename": "x.jpg"}],
            "vendor": {"id": 161072, "name": "SID Architecture"},
            "notified_at": "2026-05-25T22:22:42Z",
            "responded_at": "2026-05-25T22:22:42Z",
            "status": "unresolved",
            "manager_accepted_at": "2026-05-26T18:15:26Z",
            "user_name": "Edgar Admin",
            "updated_at": "2026-05-26T18:15:26Z",
        }
    ],
    "custom_fields": {
        "custom_field_string_def": {
            "data_type": "string",
            "value": "Custom string value that must not appear in canonical storage.",
        },
        "custom_field_decimal_def": {"data_type": "decimal", "value": 2.2},
        "custom_field_boolean_def": {"data_type": "boolean", "value": True},
        "custom_field_lov_entry_def": {
            "data_type": "lov_entry",
            "value": {"id": 1, "label": "Open"},
        },
    },
}


def test_normalize_punch_item_preserves_structured_fields_and_redacts_pii() -> None:
    record = normalize_punch_item(
        _PUNCH_RAW,
        project_key="tropical",
        endpoint_id="punch-items",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    canonical = record["canonical_fields"]
    serialized = json.dumps(record)

    # Structured fields preserved verbatim
    assert canonical["id"] == 83978
    assert canonical["name"] == "Test punch item"
    assert canonical["status"] == "Open"
    assert canonical["workflow_status"] == "initiated"
    assert canonical["cost_impact"] == "yes_known"
    assert canonical["cost_impact_amount"] == "100.0"
    assert canonical["schedule_impact_days"] == 3
    assert canonical["schedule_risk_confidence"] == 90

    # Short-label nested objects preserved
    assert canonical["location"]["id"] == 15504
    assert canonical["trade"]["name"] == "09 - acoustical panels"
    assert canonical["punch_item_type"]["id"] == 44165

    # PII reductions — names + emails NEVER in serialized output
    assert "John Doe" not in serialized
    assert "Jane Manager" not in serialized
    assert "Alex Approver" not in serialized
    assert "Carl Contractor" not in serialized
    assert "Edgar Admin" not in serialized
    assert "carl.contractor@example.com" not in serialized
    # No `@` in any people summary
    assert "@" not in serialized

    # People summaries present with counts + hashed identifiers
    assert canonical["ball_in_court_summary"]["count"] == 1
    assert canonical["ball_in_court_summary"]["hashed_identifiers"][0]["hash_prefix"]
    assert canonical["created_by_summary"]["count"] == 1
    assert canonical["assignees_summary"]["count"] == 1
    assert canonical["assignments_summary"]["count"] == 1

    # Review required because PII bearing
    assert record["review_required"] is True
    assert "pii_bearing" in record["routing_reason"]


def test_normalize_punch_item_hashes_free_text_fields() -> None:
    record = normalize_punch_item(
        _PUNCH_RAW,
        project_key="tropical",
        endpoint_id="punch-items",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    canonical = record["canonical_fields"]
    serialized = json.dumps(record)

    # description / schedule_risk_reason / assignment comment all hashed
    description_text = _PUNCH_RAW["description"]
    schedule_text = _PUNCH_RAW["schedule_risk_reason"]
    assignments_list = _PUNCH_RAW["assignments"]
    assert isinstance(assignments_list, list)
    first_assignment = assignments_list[0]
    assert isinstance(first_assignment, dict)
    comment_text = first_assignment["comment"]
    assert isinstance(description_text, str)
    assert isinstance(schedule_text, str)
    assert isinstance(comment_text, str)
    assert description_text not in serialized
    assert schedule_text not in serialized
    assert comment_text not in serialized

    # Hash summaries present
    assert "description_summary" in canonical
    assert canonical["description_summary"]["hash_prefix"]
    assert "schedule_risk_reason_summary" in canonical
    # Per-assignment comment summary
    assignment = canonical["assignments_summary"]["items"][0]
    assert "comment_summary" in assignment
    assert assignment["comment_summary"]["hash_prefix"]


def test_normalize_punch_item_custom_fields_structured_preserved_strings_hashed() -> None:
    record = normalize_punch_item(
        _PUNCH_RAW,
        project_key="tropical",
        endpoint_id="punch-items",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    canonical = record["canonical_fields"]
    serialized = json.dumps(record)

    cf_summary = canonical["custom_fields_summary"]
    assert cf_summary["count"] == 4
    fields = cf_summary["fields"]

    # Decimal preserved verbatim
    assert fields["custom_field_decimal_def"]["value"] == 2.2

    # Boolean preserved verbatim
    assert fields["custom_field_boolean_def"]["value"] is True

    # lov_entry preserved verbatim
    assert fields["custom_field_lov_entry_def"]["value"] == {"id": 1, "label": "Open"}

    # String hashed — raw text never appears
    raw_custom_fields = _PUNCH_RAW["custom_fields"]
    assert isinstance(raw_custom_fields, dict)
    raw_string_def = raw_custom_fields["custom_field_string_def"]
    assert isinstance(raw_string_def, dict)
    string_value = raw_string_def["value"]
    assert isinstance(string_value, str)
    assert string_value not in serialized
    assert "value_summary" in fields["custom_field_string_def"]
    assert fields["custom_field_string_def"]["value_summary"]["hash_prefix"]
