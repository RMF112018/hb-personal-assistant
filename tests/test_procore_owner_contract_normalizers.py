"""Phase 05 owner-side contract normalizer tests (no raw text / URL query / PII)."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.owner_contract import (
    normalize_payment_application,
    normalize_prime_change_order,
    normalize_prime_change_order_line_item,
    normalize_prime_contract,
    normalize_prime_contract_attachment,
    normalize_prime_contract_line_item,
)

_KW = {"project_key": "tropical", "correlation_id": "corr-1", "fetched_at": "2026-05-29T00:00:00Z"}


def test_prime_contract_preserves_amounts_redacts_text_and_parties() -> None:
    raw = {
        "id": 1,
        "number": "PC-001",
        "title": "Tropical Mall prime — contact bob@example.test",
        "status": "Approved",
        "executed": False,
        "private": True,
        "grand_total": "-1234567.89012345",
        "original_contract_amount": "1000000.00",
        "approved_change_orders": "250.50",
        "retainage_percent": "10.00",
        "currency_configuration": {"currency_iso_code": "USD", "currency_exchange_rate": "1.0"},
        "description": "<p>Scope: full build, call 555-123-4567</p>",
        "architect": {"id": 5, "name": "Archie A", "login": "archie@example.test"},
        "contractor": {"id": 12, "name": "Acme Concrete LLC"},
        "attachments": [{"id": 9, "filename": "c.pdf"}],
    }
    rec = normalize_prime_contract(raw, endpoint_id="prime-contracts", **_KW)
    cf = rec["canonical_fields"]
    blob = json.dumps(rec)
    assert cf["grand_total"] == "-1234567.89012345"  # decimal preserved
    assert cf["original_contract_amount"] == "1000000.00"
    assert cf["currency_iso_code"] == "USD"
    assert cf["executed"] is False and cf["private"] is True
    # free text never raw
    assert "full build" not in blob and "<p>" not in blob
    assert "bob@example.test" not in blob and "555-123-4567" not in blob
    # parties reduced to hashed refs (no raw name/email)
    assert "Archie A" not in blob and "archie@example.test" not in blob
    assert cf["architect_ref"]["hash_prefix"]
    assert rec["review_required"] is True and rec["redaction_applied"] is True


def test_prime_contract_line_item_amounts_and_wbs() -> None:
    raw = {
        "id": 50,
        "amount": "0.000000000001",
        "unit_cost": "12.50",
        "quantity": "3",
        "uom": "EA",
        "wbs_code": {"id": 7, "flat_code": "03-3000", "description": "Concrete"},
        "description": "line note",
    }
    cf = normalize_prime_contract_line_item(raw, endpoint_id="prime-contract-line-items", **_KW)[
        "canonical_fields"
    ]
    assert cf["amount"] == "0.000000000001"  # high precision preserved
    assert cf["wbs_code_id"] == "7" and cf["wbs_flat_code"] == "03-3000"
    assert "line note" not in json.dumps(cf)  # description hashed
    assert cf["description_summary"]["hash_prefix"]


def test_prime_contract_attachment_strips_url_query() -> None:
    raw = {
        "id": 9,
        "filename": "contract.pdf",
        "url": "https://files.procore.test/prostore/contract.pdf?sig=SECRET&token=ABC",
    }
    cf = normalize_prime_contract_attachment(raw, endpoint_id="prime-contract-attachments", **_KW)[
        "canonical_fields"
    ]
    blob = json.dumps(cf)
    assert cf["url_path"] == "/prostore/contract.pdf"
    assert "SECRET" not in blob and "token" not in blob and "contract.pdf" in cf["url_path"]
    assert cf["filename_summary"]["hash_prefix"]  # filename hashed, not raw


def test_prime_change_order_amounts_and_signals_fields() -> None:
    raw = {
        "id": 70,
        "number": "CO-1",
        "contract_id": 1,
        "status": "Approved",
        "executed": False,
        "paid": False,
        "signature_required": True,
        "grand_total": "5000.00",
        "schedule_impact_amount": "7",
        "review_notes": "internal note jane@example.test",
    }
    cf = normalize_prime_change_order(raw, endpoint_id="prime-change-orders", **_KW)[
        "canonical_fields"
    ]
    assert cf["grand_total"] == "5000.00" and cf["schedule_impact_amount"] == "7"
    assert cf["executed"] is False and cf["signature_required"] is True
    assert "jane@example.test" not in json.dumps(cf)  # review notes hashed


def test_prime_change_order_line_item_amount() -> None:
    cf = normalize_prime_change_order_line_item(
        {"id": 71, "amount": "-0.30", "uom": "LS"},
        endpoint_id="prime-change-order-line-items",
        **_KW,
    )["canonical_fields"]
    assert cf["amount"] == "-0.30"


def test_payment_application_reads_g702_amounts() -> None:
    raw = {
        "id": 80,
        "number": 3,
        "status": "pending",
        "percent_complete": "45.5",
        "total_amount_paid": "100000.00",
        "g702": {
            "current_payment_due": "25000.00",
            "total_retainage": "2500.00",
            "balance_to_finish_including_retainage": "874999.99",
            "contract_sum_to_date": "1000000.00",
        },
        "contract": {"id": 1, "title": "secret title"},
    }
    rec = normalize_payment_application(raw, endpoint_id="payment-applications", **_KW)
    cf = rec["canonical_fields"]
    assert cf["g702"]["current_payment_due"] == "25000.00"
    assert cf["g702"]["total_retainage"] == "2500.00"
    assert cf["total_amount_paid"] == "100000.00"
    assert cf["contract_id"] == 1
    assert "secret title" not in json.dumps(rec)  # contract.title never carried
    assert rec["review_required"] is True  # status != paid
