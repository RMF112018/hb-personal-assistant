"""Phase 04A inspections + inspection-items normalizer tests — PII hashing,
free-text hashing, attachment URL redaction, review_required heuristic."""

from __future__ import annotations

import json
import re

from hb_assistant.procore.normalizers.inspection import (
    normalize_inspection,
    normalize_inspection_item,
    normalize_inspection_section,
)

_CORRELATION = "synthetic-corr-inspection"
_FETCHED_AT = "2026-05-29T00:00:00+00:00"
_HASH_PREFIX_RE = re.compile(r"^[0-9a-f]{12}$")


# Synthetic literals — the same allowlisted shape used by the existing punch_item
# tests and by procore.fixtures. NEVER use real PII / Procore values here.
_PII_EMAIL = "synthetic-fixture@example.invalid"
_PII_NAME = "Synthetic Tester"
_PII_COMPANY = "Synthetic Co."
_FREE_TEXT_DESCRIPTION = (
    "Detailed checklist description that must not appear in canonical storage."
)


def _person(person_id: int = 160586, *, name: str = _PII_NAME) -> dict:
    return {"id": person_id, "login": _PII_EMAIL, "name": name, "company_name": _PII_COMPANY}


def _make_inspection_raw(**overrides) -> dict:
    """Build a synthetic inspections payload mirroring the operator-supplied
    example schema. All PII fields use the allowlisted synthetic literals."""
    raw = {
        "id": 42,
        "name": "Window Inspection",
        "list_template_id": 1,
        "list_template_name": "Window Inspection v2",
        "number": 1,
        "status": "Closed",
        "location": {"id": 15504, "name": "North Building", "code": "L1"},
        "created_at": "2026-05-20T00:00:00Z",
        "updated_at": "2026-05-21T00:00:00Z",
        "closed_at": "2026-05-21T00:00:00Z",
        "drawing_ids": [42],
        "current_drawing_revision_ids": [42],
        "default_response_phrasing": {
            "conforming_response": "Safe",
            "deficient_response": "At Risk",
            "global": True,
        },
        "description": _FREE_TEXT_DESCRIPTION,
        "deleted": False,
        "due_at": "2026-08-18T00:00:00Z",
        "inspection_date": "2026-05-20",
        "inspection_type": {
            "id": 142,
            "name": "Quality Compliance",
            "created_at": "2024-12-10T00:00:00Z",
        },
        "private": False,
        "created_by": _person(),
        "closed_by": _person(person_id=160587, name="Synthetic Closer"),
        "responsible_contractor": {"id": 1, "name": "Freddie's Excavating"},
        "point_of_contact": _person(person_id=160588, name="Synthetic Contact"),
        "trade": {"id": 999, "name": "09 - acoustical panels", "active": True},
        "inspectors": [_person(person_id=200001, name="Synthetic Inspector A")],
        "distribution_members": [
            _person(person_id=300001, name="Synthetic Member A")
        ],
        "signature_requests": [
            {
                "id": 21,
                "signatory": _person(person_id=400001, name="Synthetic Signer"),
                "signature": {
                    "id": 5324,
                    "captured_by": _person(person_id=400002, name="Synthetic Capturer"),
                    "captured_at": "2026-05-20T21:39:40Z",
                    "attachment": {
                        "id": 5324,
                        "url": "https://procore.example.com/signatures/jan_receipt.jpg?token=secret",
                        "filename": "jan_receipt.jpg",
                        "name": "jan_receipt.jpg",
                    },
                },
            }
        ],
        "managed_equipment_id": 1,
        "specification_section": {
            "id": 1,
            "description": "Vinyl Windows",
            "section": "08560",
        },
        "attachments": [
            {
                "id": 5324,
                "url": "https://procore.example.com/attachments/foo.pdf?token=secret",
                "thumbnail_url": "https://procore.example.com/thumbnails/foo_thumb.jpg",
                "name": "foo.pdf",
                "filename": "foo.pdf",
                "content_type": "application/pdf",
                "viewable_document_id": 492,
            }
        ],
        "conforming_item_count": 1,
        "deficient_item_count": 1,
        "not_applicable_item_count": 0,
        "neutral_item_count": 1,
        "inspected_item_count": 4,
        "observations_count": 2,
        "closed_observations_count": 1,
        "item_count": 1,
        "custom_fields": {
            "custom_field_str_def": {"data_type": "string", "value": "secret string"},
            "custom_field_dec_def": {"data_type": "decimal", "value": 2.2},
            "custom_field_bool_def": {"data_type": "boolean", "value": True},
            "custom_field_lov_def": {
                "data_type": "lov_entry",
                "value": {"id": 1, "label": "Open"},
            },
        },
        "template_id": 176,
        "overdue": False,
    }
    raw.update(overrides)
    return raw


def test_inspection_canonical_structural_keys_preserved() -> None:
    record = normalize_inspection(
        _make_inspection_raw(),
        project_key="tropical",
        endpoint_id="inspections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    cf = record["canonical_fields"]
    # All structured whitelist keys preserved.
    for key in (
        "id", "name", "number", "status", "list_template_id",
        "list_template_name", "inspection_date", "due_at", "closed_at",
        "created_at", "updated_at", "deleted", "private", "overdue",
        "conforming_item_count", "deficient_item_count",
        "not_applicable_item_count", "neutral_item_count",
        "inspected_item_count", "observations_count",
        "closed_observations_count", "item_count", "template_id",
        "managed_equipment_id",
    ):
        assert key in cf, f"missing canonical key {key!r}"
    # Structured nested objects preserved verbatim.
    assert cf["location"]["id"] == 15504
    assert cf["inspection_type"]["name"] == "Quality Compliance"
    assert cf["trade"]["id"] == 999
    assert cf["drawing_ids"] == [42]
    assert cf["default_response_phrasing"]["global"] is True


def test_inspection_pii_and_free_text_never_persists() -> None:
    record = normalize_inspection(
        _make_inspection_raw(),
        project_key="tropical",
        endpoint_id="inspections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    serialized = json.dumps(record)
    # No PII literals.
    assert _PII_EMAIL not in serialized
    assert _PII_NAME not in serialized
    assert "Synthetic Signer" not in serialized
    assert "Synthetic Capturer" not in serialized
    # No raw free-text.
    assert _FREE_TEXT_DESCRIPTION not in serialized
    # URL scheme + host + query are stripped (path-only kept). Path-only
    # URLs intentionally retain the last path segment as a source-trace
    # affordance — matches the meeting remote_meeting_url precedent.
    assert "procore.example.com" not in serialized
    assert "token=secret" not in serialized
    # The actionable `filename` field is hashed into filename_summary.
    att = record["canonical_fields"]["attachments_summary"]["items"][0]
    assert "filename_summary" in att
    assert att["url_path"] == "/attachments/foo.pdf"
    sig_att = record["canonical_fields"]["signature_requests_summary"]["items"][0]["signature"]["attachment_summary"]
    assert "filename_summary" in sig_att
    # Custom field string value never persists.
    assert "secret string" not in serialized


def test_inspection_description_hashed_to_summary_block() -> None:
    record = normalize_inspection(
        _make_inspection_raw(),
        project_key="tropical",
        endpoint_id="inspections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    desc = record["canonical_fields"]["description_summary"]
    assert desc["type"] == "string"
    assert desc["length"] == len(_FREE_TEXT_DESCRIPTION)
    assert _HASH_PREFIX_RE.match(desc["hash_prefix"])
    # Custom-fields: numeric/boolean/lov_entry preserved verbatim; string hashed.
    cf_summary = record["canonical_fields"]["custom_fields_summary"]["fields"]
    assert cf_summary["custom_field_dec_def"]["value"] == 2.2
    assert cf_summary["custom_field_bool_def"]["value"] is True
    assert cf_summary["custom_field_lov_def"]["value"]["label"] == "Open"
    assert "value_summary" in cf_summary["custom_field_str_def"]
    assert "value" not in cf_summary["custom_field_str_def"]


def test_inspection_review_required_heuristic() -> None:
    # Case 1: closed, not overdue, non-safety inspection_type → not review.
    r1 = normalize_inspection(
        _make_inspection_raw(),
        project_key="tropical",
        endpoint_id="inspections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert r1["review_required"] is False
    assert r1["routing_reason"] == "default_low_risk"
    assert r1["safety_route"] is False

    # Case 2: overdue → review (but not safety_route).
    r2 = normalize_inspection(
        _make_inspection_raw(overdue=True),
        project_key="tropical",
        endpoint_id="inspections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert r2["review_required"] is True
    assert r2["routing_reason"] == "overdue"
    assert r2["safety_route"] is False

    # Case 3: safety inspection_type → review AND safety_route.
    r3 = normalize_inspection(
        _make_inspection_raw(inspection_type={"id": 142, "name": "Safety Compliance"}),
        project_key="tropical",
        endpoint_id="inspections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert r3["review_required"] is True
    assert r3["safety_route"] is True
    assert "safety" in r3["routing_reason"]

    # Case 4: open status, non-safety type → review, no safety_route.
    r4 = normalize_inspection(
        _make_inspection_raw(status="Open"),
        project_key="tropical",
        endpoint_id="inspections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert r4["review_required"] is True
    assert r4["routing_reason"].startswith("status_contains:")
    assert r4["safety_route"] is False


def _make_inspection_item_raw(**overrides) -> dict:
    """Build a synthetic inspection-item payload mirroring the operator example.

    Sets list_id (the orchestrator dispatch sets this on each item before
    normalization, mirroring the activities pattern's schedule_id setdefault)."""
    raw = {
        "id": 2,
        "list_id": 42,
        "name": "Item 1",
        "details": "+/- 1 degrees of free-text detail that must not persist",
        "status": "yes",
        "responded_with": "Safe - Knowledge",
        "origin_id": 1,
        "section_id": 21,
        "position": 1,
        "observations": [
            {
                "id": 2085,
                "created_at": "2026-05-20T21:39:40Z",
                "number": 56,
                "status": "initiated",
                "title": "Clean up paint splatter that must be hashed",
                "type": {"id": 4952, "name": "Deficiency"},
                "assignee": _person(),
                "created_by": _person(),
            }
        ],
        "attachment_histories": [
            {
                "id": 6485,
                "created_at": "2026-05-20T21:39:40Z",
                "created_by": _person(),
                "attachment": {
                    "id": 5324,
                    "url": "https://procore.example.com/x.jpg?token=secret",
                    "filename": "x.jpg",
                },
            }
        ],
        "attachments": [
            {
                "id": 34,
                "url": "https://procore.example.com/test.pdf?token=secret",
                "filename": "test.pdf",
            }
        ],
        "histories": [
            {
                "id": 42,
                "body": "Free-text history body that must be hashed",
                "status": "yes",
                "responded_with": "Safe - Knowledge",
                "created_at": "2026-05-20T21:39:40Z",
                "created_by": _person(),
            }
        ],
        "item_response": {
            "item_id": 4323,
            "status": "conforming",
            "responded_at": "2026-05-20T21:39:40Z",
            "responder": _person(),
            "item_type": {"id": 1, "category": "multiple_choice", "name": "default"},
            "payload": {
                "text_value": "Supplies arrived at 10:00 AM — free-text",
                "number_value": 4232,
                "date_value": "2026-01-20",
                "response_option": {"id": 3432, "name": "Safe"},
            },
        },
        "comments": [
            {
                "id": 4798,
                "body": "Comment body that must be hashed.",
                "created_at": "2026-05-20T21:39:40Z",
                "created_by": _person(),
            }
        ],
        "response": {"id": 1, "name": "Safe - Knowledge", "corresponding_status": "yes"},
        "response_set_id": 9,
        "type": {"id": 1, "category": "multiple_choice", "name": "default"},
        "template_item_id": 3,
        "response_type_id": 3,
        "updated_at": "2026-05-20T21:39:40Z",
    }
    raw.update(overrides)
    return raw


def test_inspection_item_always_review_and_redacts_all_surfaces() -> None:
    record = normalize_inspection_item(
        _make_inspection_item_raw(),
        project_key="tropical",
        endpoint_id="inspection-items",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "inspection_item_default_review_required"
    assert record["parent_inspection_stable_key"] == "42"
    assert record["canonical_fields"]["parent_list_id"] == "42"

    cf = record["canonical_fields"]
    # Free-text + bodies + payload.text_value all reduce to *_summary blocks.
    assert "details_summary" in cf
    assert cf["comments_summary"]["count"] == 1
    assert "body_summary" in cf["comments_summary"]["items"][0]
    assert cf["histories_summary"]["count"] == 1
    assert "body_summary" in cf["histories_summary"]["items"][0]
    assert cf["observations_summary"]["count"] == 1
    assert "title_summary" in cf["observations_summary"]["items"][0]
    assert "text_value_summary" in cf["item_response_summary"]["payload"]
    # Non-text payload fields preserved structurally.
    assert cf["item_response_summary"]["payload"]["number_value"] == 4232
    assert cf["item_response_summary"]["payload"]["date_value"] == "2026-01-20"

    serialized = json.dumps(record)
    # Synthetic PII literals must not appear.
    assert _PII_EMAIL not in serialized
    assert _PII_NAME not in serialized
    # Raw free-text bodies must not appear.
    assert "Comment body that must be hashed" not in serialized
    assert "Free-text history body" not in serialized
    assert "Clean up paint splatter" not in serialized
    assert "Supplies arrived at 10:00" not in serialized
    # URL scheme + host + query stripped (path-only kept); filenames hashed.
    assert "procore.example.com" not in serialized
    assert "token=secret" not in serialized
    # Confirm structural redaction.
    att_items = cf["attachments_summary"]["items"]
    assert att_items[0]["url_path"] == "/test.pdf"
    assert "filename_summary" in att_items[0]
    att_hist = cf["attachment_histories_summary"]["items"][0]["attachment_summary"]
    assert att_hist["url_path"] == "/x.jpg"
    assert "filename_summary" in att_hist


def test_inspection_item_requires_list_id() -> None:
    raw = _make_inspection_item_raw()
    del raw["list_id"]
    import pytest

    with pytest.raises(ValueError):
        normalize_inspection_item(
            raw,
            project_key="tropical",
            endpoint_id="inspection-items",
            correlation_id=_CORRELATION,
            fetched_at=_FETCHED_AT,
        )


# ---------------------------------------------------------------------------
# Inspection-section normalizer — structural-only, no PII, no hashing.
# ---------------------------------------------------------------------------


def test_inspection_section_canonical_fields_preserved() -> None:
    raw = {
        "id": 21,
        "name": "Framing",
        "position": 1,
        "list_id": 42,
        "not_applicable": False,
    }
    record = normalize_inspection_section(
        raw,
        project_key="tropical",
        endpoint_id="inspection-sections",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is False
    assert record["routing_reason"] == "default_low_risk"
    assert record["safety_route"] is False
    assert record["category"] == "inspection_sections"
    assert record["entity_stable_key"] == "21"
    assert record["parent_inspection_stable_key"] == "42"
    cf = record["canonical_fields"]
    assert cf["id"] == 21
    assert cf["name"] == "Framing"
    assert cf["position"] == 1
    assert cf["list_id"] == 42
    assert cf["not_applicable"] is False
    # Nothing hashed; no PII keys ever appear.
    serialized = json.dumps(record)
    assert "hash_prefix" not in serialized


def test_inspection_section_requires_list_id() -> None:
    import pytest as _pytest

    raw = {"id": 21, "name": "Framing", "position": 1, "not_applicable": False}
    with _pytest.raises(ValueError):
        normalize_inspection_section(
            raw,
            project_key="tropical",
            endpoint_id="inspection-sections",
            correlation_id=_CORRELATION,
            fetched_at=_FETCHED_AT,
        )
