"""Runtime normalization integration with field classifiers."""

from __future__ import annotations

import pytest

from hb_assistant.forecasting.normalization import normalize_amount_field, normalize_date_field
from hb_assistant.procore.normalizers.financial import classify_amount


def test_runtime_rejects_false_positive_amount_field() -> None:
    result = normalize_amount_field(
        "allow",
        table="procore_ep_commitment_contracts",
        column="allow_payment_applications",
    )
    assert result["parse_status"] == "rejected"
    assert "field_classifier_excluded" in (result.get("rejection_reason") or "")


def test_runtime_accepts_grand_total() -> None:
    result = normalize_amount_field(
        "1000.50",
        table="procore_ep_commitment_contracts",
        column="grand_total",
    )
    assert result["parse_status"] == "parseable"
    assert result["canonical_decimal_text"] == "1000.50"


def test_classify_amount_with_table_column_guard() -> None:
    result = classify_amount(
        "5000",
        field_path="procore_ep_budget_detail_rows.job_to_date_costs",
        table="procore_ep_budget_detail_rows",
        column="job_to_date_costs",
    )
    assert result["parse_status"] == "parseable"


def test_classify_amount_rejects_invoicing_method() -> None:
    result = classify_amount(
        "progress",
        field_path="procore_ep_commitment_contracts.contract_invoicing_method",
        table="procore_ep_commitment_contracts",
        column="contract_invoicing_method",
    )
    assert result["parse_status"] == "rejected"


@pytest.mark.parametrize(
    "column",
    ["job_to_date_costs", "total_completed_and_stored_to_date"],
)
def test_runtime_date_excludes_to_date_metrics(column: str) -> None:
    result = normalize_date_field(
        "5000.00",
        table="procore_ep_subcontractor_invoice_contract_detail_items",
        column=column,
    )
    assert result["parse_as_date"] is False


def test_unknown_field_requires_review() -> None:
    result = normalize_amount_field(
        "foo",
        table="custom_table",
        column="custom_field_xyz",
    )
    assert result["parse_status"] == "review_required"