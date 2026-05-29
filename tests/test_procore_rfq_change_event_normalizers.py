"""Phase 05 RFQ / change-event normalizer tests (text hashed+excerpted, no raw PII)."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.rfq_change_event import (
    normalize_change_event,
    normalize_change_event_comment,
    normalize_rfq,
    normalize_rfq_quote,
    normalize_rfq_response,
)

_KW = {"project_key": "tropical", "correlation_id": "c1", "fetched_at": "2026-05-29T00:00:00Z"}


def test_rfq_amounts_preserved_and_text_hashed() -> None:
    raw = {
        "id": 10,
        "number": "RFQ-1",
        "status": "open",
        "estimated_amount": "-987654.32109876",
        "estimated_schedule_impact": 5,
        "estimated_status": "pending",
        "due_date": "2026-06-10",
        "intent_to_quote": True,
        "original_quote": "100000.00",
        "commitment_contract_id": 1,
        "change_event": {"id": 77, "title": "owner add"},
        "cost_code": {"id": 4, "full_code": "03-300"},
        "title": "Slab rework — call 555-111-2222",
        "description": "scope detail email sub@example.test",
        "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
        "assigned": {"id": 6, "name": "Sam", "login": "sam@example.test"},
    }
    cf = normalize_rfq(raw, endpoint_id="rfqs", **_KW)["canonical_fields"]
    blob = json.dumps(cf)
    assert cf["estimated_amount"] == "-987654.32109876"  # precision
    assert cf["original_quote"] == "100000.00" and cf["estimated_schedule_impact"] == "5"
    assert cf["intent_to_quote"] is True and cf["commitment_contract_id"] == 1
    assert cf["change_event_id"] == "77" and cf["cost_code_id"] == "4"
    assert cf["title_summary"]["hash_prefix"] and cf["description_summary"]["hash_prefix"]
    assert cf["created_by_ref"]["hash_prefix"] and cf["assigned_ref"]["hash_prefix"]
    # contact info masked in excerpts / never raw
    assert "555-111-2222" not in blob and "sub@example.test" not in blob
    assert "Pat" not in blob and "pat@example.test" not in blob


def test_rfq_quote_cost_and_schedule_and_description() -> None:
    cf = normalize_rfq_quote(
        {
            "id": 3,
            "request_for_quote_id": 10,
            "cost": "0.000000000001",
            "schedule_impact": 2,
            "description": "vendor quote note contact bid@example.test",
            "created_by": {"id": 9, "name": "Lee", "login": "lee@example.test"},
        },
        endpoint_id="rfq-quotes",
        **_KW,
    )["canonical_fields"]
    assert cf["cost"] == "0.000000000001" and cf["schedule_impact"] == "2"  # precision
    assert cf["request_for_quote_id"] == 10
    assert cf["description_summary"]["hash_prefix"]
    assert "bid@example.test" not in json.dumps(cf) and "Lee" not in json.dumps(cf)


def test_rfq_response_comment_hashed() -> None:
    cf = normalize_rfq_response(
        {
            "id": 2,
            "request_for_quote_id": 10,
            "comment": "we will respond, reach me at 555-222-3333",
            "created_by": {"id": 9, "name": "Lee", "login": "lee@example.test"},
            "attachments": [{"id": 1, "name": "a.pdf", "url": "https://x.test/a.pdf?sig=Z"}],
        },
        endpoint_id="rfq-responses",
        **_KW,
    )["canonical_fields"]
    blob = json.dumps(cf)
    assert cf["comment_summary"]["hash_prefix"] and cf["attachments_count"] == 1
    assert "555-222-3333" not in blob and "lee@example.test" not in blob and "sig=Z" not in blob


def test_change_event_amounts_preserved_and_title_hashed() -> None:
    raw = {
        "id": 77,
        "number": 12,
        "status": "open",
        "scope": "in_scope",
        "estimated_cost": "250000.00",
        "estimated_revenue": "300000.00",
        "owner_cost_amount": "0.000000000001",
        "commitment_cost_amount": "240000.00",
        "schedule_impact_amount": 7,
        "title": "Foundation redesign — owner@example.test",
        "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
    }
    cf = normalize_change_event(raw, endpoint_id="change-events", **_KW)["canonical_fields"]
    blob = json.dumps(cf)
    assert cf["estimated_cost"] == "250000.00" and cf["estimated_revenue"] == "300000.00"
    assert cf["owner_cost_amount"] == "0.000000000001"  # precision
    assert cf["schedule_impact_amount"] == "7" and cf["scope"] == "in_scope"
    assert cf["title_summary"]["hash_prefix"] and cf["created_by_ref"]["hash_prefix"]
    assert "owner@example.test" not in blob and "Pat" not in blob


def test_change_event_comment_body_hashed() -> None:
    cf = normalize_change_event_comment(
        {
            "id": "c1",
            "body": "discussion note, email me at note@example.test",
            "creator": {"id": 5, "name": "Pat", "login": "pat@example.test"},
            "created_at": "2026-05-20T00:00:00Z",
        },
        endpoint_id="change-event-comments",
        **_KW,
    )["canonical_fields"]
    blob = json.dumps(cf)
    assert cf["body_summary"]["hash_prefix"] and cf["creator_ref"]["hash_prefix"]
    assert "note@example.test" not in blob and "Pat" not in blob
