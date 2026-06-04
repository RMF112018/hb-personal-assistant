# 08 Financial Data Structure Quality Evidence

This file is part of an evaluation evidence packet. It records measurable evidence only and does not conclude that the underlying data is usable, meaningful, high quality, or production-ready.

## Machine-Readable Summary

```json
{
  "financial_determinations_made": false,
  "financial_field_usefulness_indicators": [
    {
      "field": "amount_fact_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "amount_name",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "amount_value",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "currency_iso_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "base_currency_iso_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "period_start",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.987138,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "period_end",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.987138,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "wbs_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.033758,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "cost_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.033758,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "source_field_path",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "created_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_amount_facts"
    },
    {
      "field": "billing_period_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "billing_period_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "start_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.782609
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "end_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.695652
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "due_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.695652
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "position",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.695652
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_billing_periods"
    },
    {
      "field": "budget_change_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "budget_change_kind",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "budget_change_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "budget_view_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "parent_change_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "number",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 379,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "title_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.395778,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "wbs_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "wbs_flat_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.395778,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "cost_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "adjustment_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.522427,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "from_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.395778,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "to_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.395778,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "approved_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.968338
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.968338
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_changes"
    },
    {
      "field": "budget_row_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "budget_view_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "row_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "wbs_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "wbs_flat_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "cost_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "line_item_type_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "column_values_json_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_rows"
    },
    {
      "field": "budget_view_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "budget_view_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "name_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "description_summary_json",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 1.0
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_budget_views"
    },
    {
      "field": "record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "change_event_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "number",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "title_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "scope",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "estimated_cost",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "estimated_revenue",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "schedule_impact_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "owner_cost_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "commitment_cost_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.822917
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_events"
    },
    {
      "field": "line_item_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "change_order_record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "line_item_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "change_order_family",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "description_summary_json",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "wbs_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "wbs_flat_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "cost_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "line_item_type_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "quantity",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "uom",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.788321,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "unit_cost",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "position",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "currency_iso_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_order_line_items"
    },
    {
      "field": "record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "change_order_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "change_order_family",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "contract_record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "contract_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "number",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "title_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "executed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "paid",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "private",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "field_change",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "signature_required",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "grand_total",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "schedule_impact_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.646341,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "due_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 133,
        "null_rate": 0.810976,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.189024
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "invoiced_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 164,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "paid_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 164,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "reviewed_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": true,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 23,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 23,
        "null_rate": 0.140244,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.762195
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.847561
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_change_orders"
    },
    {
      "field": "compliance_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "contract_record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "compliance_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "document_type",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "compliant",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "effective_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 105,
        "null_rate": 0.187835,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.726297
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "expiration_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 113,
        "null_rate": 0.202147,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.239714
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "attachment_path_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.039356,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "notes_summary_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.923077,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 559,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_compliance_documents"
    },
    {
      "field": "record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "contract_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "contract_family",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "contract_type",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.098684,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "number",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "title_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.006579,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "executed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "private",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "accounting_method",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.973684,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "vendor_entity_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "company_entity_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "grand_total",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "original_contract_sum",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "revised_contract_sum",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.973684,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "approved_change_orders_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.973684,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "pending_change_orders_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "retainage_percent",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "currency_iso_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "base_currency_iso_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "currency_exchange_rate",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "contract_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 152,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "start_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 152,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "completion_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 152,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.203947
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "last_sync_run_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_contracts"
    },
    {
      "field": "invoice_item_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "invoice_record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "requisition_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "item_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "item_type",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "line_item_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.930496,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "cost_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "wbs_flat_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "description_summary_json",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.002132,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "scheduled_value",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "work_completed_this_period",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "materials_presently_stored",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.069275,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "total_completed_and_stored_to_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.627588
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "retainage_held",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "subcontractor_claimed_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "position",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_invoice_items"
    },
    {
      "field": "line_item_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "parent_record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "line_item_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "line_item_kind",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "description_summary_json",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "wbs_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "wbs_flat_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.010178,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "wbs_description_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.010178,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "cost_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.888041,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "line_item_type_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "tax_code_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "quantity",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.776081,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "uom",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.821883,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "unit_cost",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.776081,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "scheduled_value",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "billed_to_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 393,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "work_completed_this_period",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "materials_presently_stored",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "retainage_held",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "position",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "currency_iso_code",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_line_items"
    },
    {
      "field": "record_key",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "payment_application_id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "contract_record_key",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "prime_contract_id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "billing_period_id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "invoice_number",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "number",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "billing_date",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "period_start",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "period_end",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "percent_complete",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "current_payment_due",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "total_amount_paid",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "total_retainage",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "balance_to_finish_including_retainage",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "contract_sum_to_date",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_payment_applications"
    },
    {
      "field": "record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "rfq_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "commitment_contract_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "number",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "title_redacted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "private",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "due_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.857143
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "estimated_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "estimated_schedule_impact",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "estimated_status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "intent_to_quote",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.428571,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "original_quote",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.714286
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_rfqs"
    },
    {
      "field": "record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "invoice_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "commitment_record_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "commitment_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "billing_period_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "billing_period_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "previous_invoice_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.195455,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "vendor_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "vendor_entity_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "invoice_number",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "number",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "invoice_type",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "final",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "billing_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.740909
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "period_start",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "period_end",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "percent_complete",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "payment_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 220,
        "null_rate": 1.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.0
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "submitted_at",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 135,
        "null_rate": 0.613636,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.3
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "erp_status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "current_payment_due",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "total_claimed_amount",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "original_contract_sum",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "contract_sum_to_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.222727
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "total_completed_and_stored_to_date",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.304545
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "total_retainage",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "total_earned_less_retainage",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "balance_to_finish_including_retainage",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "updated_at_utc",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": 0.663636
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "raw_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "redaction_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "source_family",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "source_table",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "source_record_ref",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "source_field_path",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "source_value_hash",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "parse_status",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "canonical_decimal_text",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "minor_units",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "currency_code",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "currency_status",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "rejection_reason",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "confidence_label",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": 0,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "review_tier",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "currency_status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "project_default_applied",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "evidence_backed_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "inconsistent_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "missing_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "exposure_category",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "item_label",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "normalized_amount_ref",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "confidence_label",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": 0,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "review_tier",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "advisory_status",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "started_utc",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "completed_utc",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": 0,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "notes_redacted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": null,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": null,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 37,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "readiness_status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "gate_status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "context_items_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "review_items_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 30,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.9375,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "items_evaluated",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "review_required_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "trigger_category",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "source_ref",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 537,
        "missing_timestamp_count": null,
        "null_rate": 0.008085,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "amount_ref",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.991915,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "review_tier",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "confidence_label",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": 78,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.001174,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_review_required_items"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "source_family",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "endpoint_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 1.0,
        "orphan_reference_risk": true,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "local_table",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "live_verification_status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "coverage_status",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "row_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "amount_field_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "currency_field_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "wbs_cost_code_field_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "relationship_key_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "field": "id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "run_id",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "project_key",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": 0,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "wbs_present_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "cost_code_present_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "line_item_type_present_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "missing_wbs_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "missing_cost_code_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "ambiguous_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "review_required_count",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "advisory_only",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "raw_email_body_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "raw_document_text_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "raw_calendar_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "raw_procore_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "raw_financial_source_payload_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "raw_prompt_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "raw_response_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "signed_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "download_url_persisted",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": true,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "external_writeback_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": 0,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "financial_determination_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": null,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "payment_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    },
    {
      "field": "claim_or_entitlement_decision_performed",
      "indicators": {
        "empty_rate": 0.0,
        "inconsistent_enum_values_indicator": false,
        "json_key_drift_indicator": false,
        "likely_raw_content_risk_field": false,
        "missing_confidence_label_count": null,
        "missing_project_link_count": null,
        "missing_review_status_count": 0,
        "missing_source_reference_count": null,
        "missing_timestamp_count": null,
        "null_rate": 0.0,
        "orphan_reference_risk": false,
        "stale_date_rate_90d": null
      },
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    }
  ],
  "financial_row_count_total": 169401,
  "financial_table_count": 24,
  "financial_tables": [
    {
      "column_count": 15,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "amount_name",
        "raw_body_persisted"
      ],
      "row_count": 85521,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_amount_facts"
    },
    {
      "column_count": 12,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 23,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_billing_periods"
    },
    {
      "column_count": 20,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 379,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_budget_changes"
    },
    {
      "column_count": 12,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 1182,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_budget_rows"
    },
    {
      "column_count": 8,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name_redacted",
        "raw_body_persisted"
      ],
      "row_count": 17,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_budget_views"
    },
    {
      "column_count": 16,
      "functional_area": "calendar",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 192,
      "source_families": [
        "calendar",
        "procore",
        "financial"
      ],
      "table": "procore_financial_change_events"
    },
    {
      "column_count": 19,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 274,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_change_order_line_items"
    },
    {
      "column_count": 24,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 164,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_change_orders"
    },
    {
      "column_count": 15,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "attachment_path_redacted",
        "raw_body_persisted"
      ],
      "row_count": 559,
      "source_families": [
        "sharepoint_onedrive",
        "procore",
        "financial"
      ],
      "table": "procore_financial_compliance_documents"
    },
    {
      "column_count": 30,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 152,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_contracts"
    },
    {
      "column_count": 21,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 13136,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_invoice_items"
    },
    {
      "column_count": 26,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 393,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_line_items"
    },
    {
      "column_count": 22,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_payment_applications"
    },
    {
      "column_count": 18,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 7,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_rfqs"
    },
    {
      "column_count": 34,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 220,
      "source_families": [
        "procore",
        "financial"
      ],
      "table": "procore_financial_subcontractor_invoices"
    },
    {
      "column_count": 30,
      "functional_area": "financial facts and readiness",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "canonical_decimal_text",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "financial"
      ],
      "table": "second_brain_financial_amount_facts_normalized"
    },
    {
      "column_count": 22,
      "functional_area": "financial facts and readiness",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 147,
      "source_families": [
        "financial"
      ],
      "table": "second_brain_financial_currency_completeness_snapshots"
    },
    {
      "column_count": 23,
      "functional_area": "financial facts and readiness",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "financial"
      ],
      "table": "second_brain_financial_exposure_summary_items"
    },
    {
      "column_count": 21,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "financial"
      ],
      "table": "second_brain_financial_fact_normalization_runs"
    },
    {
      "column_count": 21,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "context_items_count",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 37,
      "source_families": [
        "financial"
      ],
      "table": "second_brain_financial_forecast_readiness_runs"
    },
    {
      "column_count": 20,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 32,
      "source_families": [
        "financial",
        "agent_receipts"
      ],
      "table": "second_brain_financial_readiness_agent_runs"
    },
    {
      "column_count": 22,
      "functional_area": "financial facts and readiness",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 66417,
      "source_families": [
        "financial",
        "review_queue"
      ],
      "table": "second_brain_financial_review_required_items"
    },
    {
      "column_count": 27,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 500,
      "source_families": [
        "financial"
      ],
      "table": "second_brain_financial_source_coverage_snapshots"
    },
    {
      "column_count": 24,
      "functional_area": "financial facts and readiness",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 49,
      "source_families": [
        "financial"
      ],
      "table": "second_brain_financial_wbs_cost_code_snapshots"
    }
  ]
}
```
