"""Phase 05 budget normalizer tests (amounts preserved, free text hashed, columns kept)."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.budget import (
    normalize_budget_change_history,
    normalize_budget_change_line_item,
    normalize_budget_detail_column,
    normalize_budget_detail_row,
    normalize_budget_modification,
    normalize_budget_view,
)

_KW = {"project_key": "tropical", "correlation_id": "c1", "fetched_at": "2026-05-29T00:00:00Z"}


def test_budget_view_keeps_name_hashes_description() -> None:
    cf = normalize_budget_view(
        {
            "id": 1,
            "name": "Detailed Budget",
            "description": "internal note contact pm@example.test",
            "created_by": {"id": 5, "name": "Pat", "login": "pat@example.test"},
            "links": {"detail_rows": "https://x.test/rows?sig=Z"},
        },
        endpoint_id="budget-views",
        **_KW,
    )["canonical_fields"]
    blob = json.dumps(cf)
    assert cf["name"] == "Detailed Budget"  # label kept
    assert cf["description_summary"]["hash_prefix"] and cf["created_by_ref"]["hash_prefix"]
    assert "pm@example.test" not in blob and "Pat" not in blob and "sig=Z" not in blob


def test_budget_detail_column_keeps_definition_fields() -> None:
    cf = normalize_budget_detail_column(
        {
            "id": "col_1",
            "name": "Projected Costs",
            "type": "currency",
            "position": 3,
            "aggregatable": True,
            "filterable": True,
            "groupable": False,
        },
        endpoint_id="budget-detail-columns",
        **_KW,
    )["canonical_fields"]
    assert cf["name"] == "Projected Costs" and cf["type"] == "currency" and cf["position"] == 3
    assert cf["aggregatable"] is True


def test_budget_detail_row_amounts_and_hashed_text() -> None:
    raw = {
        "id": 9,
        "cost_code_id": 4,
        "wbs_code_id": 3,
        "original_budget_amount": "1000000.00",
        "projected_costs": "0.000000000001",
        "budget_forecast": {"amount": "1100000.00", "notes": "ahead, call 555-111-2222"},
        "unbudgeted_reason": "see email pm@example.test",
        "currency_configuration": {"currency_iso_code": "USD"},
    }
    cf = normalize_budget_detail_row(raw, endpoint_id="budget-detail-rows", **_KW)[
        "canonical_fields"
    ]
    blob = json.dumps(cf)
    assert cf["original_budget_amount"] == "1000000.00"
    assert cf["projected_costs"] == "0.000000000001"  # precision
    assert cf["budget_forecast"]["amount"] == "1100000.00"
    assert cf["wbs_code_id"] == "3" and cf["cost_code_id"] == "4"
    assert cf["budget_forecast"]["notes_summary"]["hash_prefix"]
    assert cf["unbudgeted_reason_summary"]["hash_prefix"]
    assert "555-111-2222" not in blob and "pm@example.test" not in blob


def test_budget_change_history_old_new_amounts() -> None:
    cf = normalize_budget_change_history(
        {
            "budget_code": "01-100",
            "column": "Revised Budget",
            "type": "adjustment",
            "old_value": "100.00",
            "new_value": "150.50",
            "description": "bump",
            "created_at": "2026-05-20",
            "created_by": {"id": 5, "name": "Pat"},
        },
        endpoint_id="budget-change-history",
        **_KW,
    )["canonical_fields"]
    assert cf["old_value"] == "100.00" and cf["new_value"] == "150.50"
    assert cf["budget_code"] == "01-100" and cf["column"] == "Revised Budget"
    assert cf["description_summary"]["hash_prefix"] and cf["created_by_ref"]["hash_prefix"]


def test_budget_change_line_item_amount() -> None:
    cf = normalize_budget_change_line_item(
        {
            "id": 7,
            "budget_change_id": "bc1",
            "budget_change_number": "BC-1",
            "budget_change_status": "approved",
            "amount": "5000.00",
            "wbs_code_id": "3",
            "description": "extra",
        },
        endpoint_id="budget-change-line-items",
        **_KW,
    )["canonical_fields"]
    assert cf["amount"] == "5000.00" and cf["budget_change_status"] == "approved"
    assert cf["wbs_code_id"] == "3"


def test_budget_modification_transfer_amount() -> None:
    cf = normalize_budget_modification(
        {
            "id": 11,
            "from_budget_line_item_id": 100,
            "to_budget_line_item_id": 200,
            "transfer_amount": "2500.00",
            "notes": "reallocate per pm@example.test",
            "created_at": "2026-05-21",
        },
        endpoint_id="budget-modifications",
        **_KW,
    )["canonical_fields"]
    blob = json.dumps(cf)
    assert cf["transfer_amount"] == "2500.00"
    assert cf["from_budget_line_item_id"] == 100 and cf["to_budget_line_item_id"] == 200
    assert cf["notes_summary"]["hash_prefix"] and "pm@example.test" not in blob
