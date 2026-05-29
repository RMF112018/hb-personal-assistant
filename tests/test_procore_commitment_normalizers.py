"""Phase 05 vendor-side normalizer tests (no raw notes / URL query / PII)."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.commitment_contract import (
    normalize_commitment_attachment,
    normalize_commitment_change_order,
    normalize_commitment_change_order_line_item,
    normalize_commitment_compliance,
    normalize_commitment_contract,
    normalize_commitment_line_item,
    normalize_purchase_order_contract,
    normalize_purchase_order_detail_line_item,
    normalize_purchase_order_line_item,
)

_KW = {"project_key": "tropical", "correlation_id": "c1", "fetched_at": "2026-05-29T00:00:00Z"}


def test_commitment_contract_amounts_redacts_text_and_parties() -> None:
    raw = {
        "id": 1,
        "number": "SC-001",
        "type": "WorkOrderContract",
        "status": "Pending",
        "executed": False,
        "grand_total": "-987654.32109876",
        "retainage_percent": "5.00",
        "currency_configuration": {"currency_iso_code": "USD"},
        "title": "Concrete subcontract — call 555-999-0000",
        "description": "scope details with secret@example.test",
        "vendor": {"id": 12, "name": "Acme Concrete LLC"},
        "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
    }
    rec = normalize_commitment_contract(raw, endpoint_id="commitment-contracts", **_KW)
    cf = rec["canonical_fields"]
    blob = json.dumps(rec)
    assert cf["grand_total"] == "-987654.32109876"  # decimal preserved
    assert cf["retainage_percent"] == "5.00" and cf["currency_iso_code"] == "USD"
    assert cf["executed"] is False and cf["vendor_id"] == 12
    assert "scope details" not in blob and "secret@example.test" not in blob
    assert "555-999-0000" not in blob and "Pat" not in blob and "pat@example.test" not in blob
    assert cf["created_by_ref"]["hash_prefix"]


def test_commitment_line_item_amount_and_wbs() -> None:
    cf = normalize_commitment_line_item(
        {"id": 9, "amount": "0.000000000001", "wbs_code": {"id": 3, "flat_code": "01-100"}},
        endpoint_id="commitment-line-items",
        **_KW,
    )["canonical_fields"]
    assert cf["amount"] == "0.000000000001" and cf["wbs_code_id"] == "3"


def test_commitment_attachment_strips_url_query() -> None:
    cf = normalize_commitment_attachment(
        {"id": 7, "name": "coi.pdf", "url": "https://x.test/coi.pdf?sig=SECRET&token=A"},
        endpoint_id="commitment-attachments",
        **_KW,
    )["canonical_fields"]
    assert cf["url_path"] == "/coi.pdf"
    assert "SECRET" not in json.dumps(cf) and "token" not in json.dumps(cf)


def test_commitment_compliance_keeps_status_hashes_notes() -> None:
    raw = {
        "contract_id": 1,
        "compliance_status": "non_compliant",
        "insurance_status": "compliant",
        "compliance_notes": "missing W9, email vendor@example.test",
        "compliance_documents": [
            {
                "id": 11,
                "type": "W9",
                "status": "expired",
                "expires_at": "2025-01-01",
                "notes": "expired cert",
                "attachments": [{"url": "https://x.test/w9.pdf?sig=Z"}],
            },
        ],
        "insurance_documents": [
            {"id": 21, "insurance_type": "GL", "status": "active", "expires_at": "2027-01-01"},
        ],
    }
    rec = normalize_commitment_compliance(raw, endpoint_id="commitment-compliance", **_KW)
    cf = rec["canonical_fields"]
    blob = json.dumps(rec)
    assert cf["compliance_status"] == "non_compliant" and cf["insurance_status"] == "compliant"
    assert cf["compliance_document_count"] == 1 and cf["insurance_document_count"] == 1
    # notes never raw; document status metadata preserved
    assert (
        "missing W9" not in blob
        and "vendor@example.test" not in blob
        and "expired cert" not in blob
    )
    assert cf["compliance_notes_summary"]["hash_prefix"]
    assert cf["compliance_documents"][0]["status"] == "expired"
    assert cf["compliance_documents"][0]["expires_at"] == "2025-01-01"


def test_commitment_change_order_amounts_redacts_text_and_parties() -> None:
    raw = {
        "id": 30,
        "number": "CCO-002",
        "contract_id": 1,
        "status": "Pending",
        "executed": False,
        "paid": False,
        "signature_required": True,
        "grand_total": "-12345.6789012345",
        "schedule_impact_amount": 7,
        "currency_configuration": {"currency_iso_code": "USD"},
        "title": "Added scope — call 555-222-3333",
        "description": "extra work for owner@example.test",
        "review_notes": "approve after review by ann@example.test",
        "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
        "received_from": {"id": 6, "name": "Sam", "login": "sam@example.test"},
        "due_date": "2026-06-30",
        "invoiced_date": "2026-06-01",
    }
    rec = normalize_commitment_change_order(raw, endpoint_id="commitment-change-orders", **_KW)
    cf = rec["canonical_fields"]
    blob = json.dumps(rec)
    assert cf["grand_total"] == "-12345.6789012345"  # decimal preserved
    assert cf["schedule_impact_amount"] == "7" and cf["currency_iso_code"] == "USD"
    assert cf["contract_id"] == 1 and cf["executed"] is False and cf["signature_required"] is True
    assert cf["due_date"] == "2026-06-30" and cf["invoiced_date"] == "2026-06-01"
    # free text + party PII never raw
    assert "Added scope" not in blob and "extra work" not in blob
    assert "555-222-3333" not in blob and "owner@example.test" not in blob
    assert "ann@example.test" not in blob and "Pat" not in blob and "pat@example.test" not in blob
    assert cf["created_by_ref"]["hash_prefix"] and cf["received_from_ref"]["hash_prefix"]


def test_commitment_co_line_item_keeps_amount_and_change_event_linkage() -> None:
    raw = {
        "id": 99,
        "amount": "0.000000000001",
        "unit_cost": "1.25",
        "quantity": 3,
        "commitment_line_item_id": 5,
        "prime_line_item_id": 8,
        "wbs_code": {"id": 3, "flat_code": "01-100", "description": "Concrete"},
        "description": "line note with ce-vendor@example.test",
        "change_event_line_item": {
            "id": 700,
            "description": "CE scope contact 555-444-5555",
            "event": {"id": 42, "number": "CE-007", "title": "Owner request mike@example.test"},
            "wbs_code": {"id": 9, "flat_code": "02-200"},
        },
    }
    cf = normalize_commitment_change_order_line_item(
        raw, endpoint_id="commitment-change-order-line-items", **_KW
    )["canonical_fields"]
    blob = json.dumps(cf)
    assert cf["amount"] == "0.000000000001"  # precision preserved
    assert cf["wbs_code_id"] == "3" and cf["wbs_flat_code"] == "01-100"
    assert cf["commitment_line_item_id"] == "5" and cf["prime_line_item_id"] == "8"
    cel = cf["change_event_line_item"]
    assert cel["change_event_line_item_id"] == "700" and cel["change_event_id"] == "42"
    assert cel["change_event_number"] == "CE-007" and cel["wbs_code_id"] == "9"
    # free text inside the linkage never raw
    assert "Owner request" not in blob and "mike@example.test" not in blob
    assert "CE scope" not in blob and "555-444-5555" not in blob
    assert "line note" not in blob and "ce-vendor@example.test" not in blob


def test_purchase_order_contract_fields() -> None:
    raw = {
        "id": 50,
        "number": "PO-9",
        "status": "Processing",
        "executed": True,
        "grand_total": "12345.67",
        "delivery_date": "2026-06-05",
        "vendor": {"id": 12, "company": "Acme"},
        "ship_to_address": "123 Jobsite Rd, call 555-111-2222",
    }
    cf = normalize_purchase_order_contract(raw, endpoint_id="purchase-order-contracts", **_KW)[
        "canonical_fields"
    ]
    assert cf["grand_total"] == "12345.67" and cf["status"] == "Processing"
    assert cf["delivery_date"] == "2026-06-05" and cf["vendor_id"] == 12
    assert "555-111-2222" not in json.dumps(cf)  # address hashed


def test_purchase_order_line_and_detail_amounts() -> None:
    li = normalize_purchase_order_line_item(
        {"id": 1, "amount": "-1.50", "total_amount": "100.00"},
        endpoint_id="purchase-order-line-items",
        **_KW,
    )["canonical_fields"]
    assert li["amount"] == "-1.50"
    detail = normalize_purchase_order_detail_line_item(
        {"id": 2, "line_item_id": 1, "amount": "0.30", "billed_to_date": "2026-05-01"},
        endpoint_id="purchase-order-detail-line-items",
        **_KW,
    )["canonical_fields"]
    assert detail["amount"] == "0.30" and detail["line_item_id"] == 1
