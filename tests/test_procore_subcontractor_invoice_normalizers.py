"""Phase 05 subcontractor-billing normalizer tests (no address/contact/PII raw)."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.subcontractor_invoice import (
    normalize_billing_period,
    normalize_subcontractor_invoice,
    normalize_subcontractor_invoice_change_order_item,
    normalize_subcontractor_invoice_contract_detail_item,
    normalize_subcontractor_invoice_contract_item,
)

_KW = {"project_key": "tropical", "correlation_id": "c1", "fetched_at": "2026-05-29T00:00:00Z"}


def test_billing_period_keeps_status_and_dates() -> None:
    cf = normalize_billing_period(
        {
            "id": 7,
            "status": "open",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "due_date": "2026-06-05",
            "position": 3,
        },
        endpoint_id="billing-periods",
        **_KW,
    )["canonical_fields"]
    assert cf["status"] == "open" and cf["due_date"] == "2026-06-05"
    assert cf["start_date"] == "2026-05-01" and cf["position"] == 3


def test_subcontractor_invoice_excludes_address_keeps_amounts_hashes_creator() -> None:
    raw = {
        "id": 40,
        "number": 5,
        "invoice_number": 5,
        "invoice_type": "Standard",
        "status": "under_review",
        "final": False,
        "commitment_id": 1,
        "vendor_id": 12,
        "vendor_name": "Acme Concrete LLC",
        "period_id": 7,
        "previous_requisition_id": 39,
        "requisition_start": "2026-05-01",
        "requisition_end": "2026-05-31",
        "currency_configuration": {"currency_iso_code": "USD"},
        "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
        "total_claimed_amount": "250000.00",
        "summary": {
            "current_payment_due": "100000.00",
            "total_retainage": "5000.00",
            "total_completed_and_stored_to_date": "0.000000000001",
        },
        "summary_text": {
            "subcontractor_name": "Acme Concrete LLC",
            "subcontractor_street": "123 Jobsite Rd",
            "subcontractor_city": "Tampa",
            "subcontractor_zip": "33601",
            "to_general_contractor": "call 555-111-2222 / gc@example.test",
        },
    }
    rec = normalize_subcontractor_invoice(raw, endpoint_id="subcontractor-invoices", **_KW)
    cf = rec["canonical_fields"]
    blob = json.dumps(rec)
    assert cf["status"] == "under_review" and cf["commitment_id"] == 1 and cf["vendor_id"] == 12
    assert cf["vendor_name"] == "Acme Concrete LLC"  # organisation label kept
    assert cf["summary"]["current_payment_due"] == "100000.00"
    assert cf["summary"]["total_completed_and_stored_to_date"] == "0.000000000001"  # precision
    assert cf["total_claimed_amount"] == "250000.00"
    assert cf["created_by_ref"]["hash_prefix"]  # creator hashed
    # address / contact content never persists; creator PII never raw
    assert "123 Jobsite Rd" not in blob and "33601" not in blob and "Tampa" not in blob
    assert "555-111-2222" not in blob and "gc@example.test" not in blob
    assert "Pat" not in blob and "pat@example.test" not in blob
    assert "summary_text" not in cf


def test_invoice_items_keep_amounts_and_hash_description() -> None:
    base = {
        "id": 1,
        "status": "approved",
        "item_type": "standard",
        "line_item_id": 9,
        "cost_code_id": 4,
        "scheduled_value": "100000.00",
        "work_completed_this_period": "25000.00",
        "materials_presently_stored": "1000.00",
        "total_completed_and_stored_to_date": "0.000000000001",
        "subcontractor_claimed_amount": "26000.00",
        "work_completed_retainage_retained_this_period": "2600.00",
        "wbs_code": {"id": 3, "flat_code": "01-100", "description": "Concrete"},
        "description_of_work": "pour slab — questions to super@example.test",
        "comment": "call 555-333-4444",
    }
    for fn, endpoint in (
        (normalize_subcontractor_invoice_contract_item, "subcontractor-invoice-contract-items"),
        (
            normalize_subcontractor_invoice_contract_detail_item,
            "subcontractor-invoice-contract-detail-items",
        ),
        (
            normalize_subcontractor_invoice_change_order_item,
            "subcontractor-invoice-change-order-items",
        ),
    ):
        cf = fn(base, endpoint_id=endpoint, **_KW)["canonical_fields"]
        blob = json.dumps(cf)
        assert cf["scheduled_value"] == "100000.00"
        assert cf["total_completed_and_stored_to_date"] == "0.000000000001"  # precision
        assert cf["wbs_code_id"] == "3" and cf["wbs_flat_code"] == "01-100"
        assert cf["description_of_work_summary"]["hash_prefix"]
        assert "pour slab" not in blob and "super@example.test" not in blob
        assert "555-333-4444" not in blob
