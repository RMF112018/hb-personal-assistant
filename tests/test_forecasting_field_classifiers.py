"""Tests for forecasting field classifiers (amount/date/boolean/status)."""

from __future__ import annotations

import pytest

from hb_assistant.forecasting.field_classifiers import (
    classify_amount_field,
    classify_date_field,
    normalize_boolean_value,
    normalize_status_group,
)


@pytest.mark.parametrize(
    "column",
    [
        "budget_impact_source_of_latest_budget_impact",
        "cost_impact_source_of_stage",
        "contract_invoicing_method",
        "allow_payment_applications",
        "display_work_retainage",
    ],
)
def test_amount_false_positives_excluded(column: str) -> None:
    result = classify_amount_field(table="procore_ep_change_events_change_items", column=column)
    assert result["kind"] == "excluded_false_positive"
    assert result["approved_for_aggregation"] is False


@pytest.mark.parametrize(
    "column",
    [
        "grand_total",
        "latest_cost_values_amount",
        "scheduled_value",
        "subcontractor_claimed_amount",
        "job_to_date_costs",
        "actual_cost",
    ],
)
def test_amount_true_monetary_included(column: str) -> None:
    result = classify_amount_field(table="procore_ep_budget_detail_rows", column=column)
    assert result["approved_for_aggregation"] is True
    assert result["kind"] in {"true_monetary_amount", "unknown"}


def test_date_to_date_metrics_not_parsed() -> None:
    for column in (
        "total_completed_and_stored_to_date",
        "job_to_date_costs",
        "erp_job_to_date_costs",
        "work_completed_from_previous_application",
    ):
        result = classify_date_field(
            table="procore_ep_subcontractor_invoice_contract_detail_items",
            column=column,
        )
        assert result["kind"] == "non_date_to_date_metric"
        assert result["parse_as_date"] is False


def test_date_true_timestamps_parsed() -> None:
    result = classify_date_field(table="procore_ep_billing_periods", column="start_date")
    assert result["parse_as_date"] is True
    assert result["kind"] in {"billing_period_start_end", "business_event_date"}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1", True),
        ("0", False),
        ("true", True),
        ("false", False),
        ("True", True),
        ("False", False),
        (None, None),
        ("", None),
        ("maybe", None),
    ],
)
def test_boolean_normalization(raw, expected) -> None:
    result = normalize_boolean_value(raw)
    assert result["normalized"] is expected
    if raw in (None, "", "maybe"):
        assert result.get("requires_review") in (None, True)


@pytest.mark.parametrize(
    "status,expected_inclusion",
    [
        ("approved", "included_actual_approved"),
        ("complete", "included_actual_approved"),
        ("draft", "pending_probability_weighted"),
        ("pending", "pending_probability_weighted"),
        ("void", "excluded_void"),
        ("cancelled", "excluded_void"),
    ],
)
def test_status_inclusion_groups(status: str, expected_inclusion: str) -> None:
    result = normalize_status_group(status, table_family="commitment")
    assert result["inclusion_logic"] == expected_inclusion