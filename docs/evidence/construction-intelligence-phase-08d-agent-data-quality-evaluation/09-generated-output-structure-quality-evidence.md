# 09 Generated Output Structure Quality Evidence

This file is part of an evaluation evidence packet. It records measurable evidence only and does not conclude that the underlying data is usable, meaningful, high quality, or production-ready.

## Machine-Readable Summary

```json
{
  "content_quality_evaluated": false,
  "generated_output_row_count_total": 0,
  "generated_output_table_count": 10,
  "generated_output_tables": [
    {
      "column_count": 21,
      "functional_area": "daily briefs",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "content_hash",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "daily_brief",
        "automation",
        "agent_receipts"
      ],
      "table": "daily_brief_delivery_receipts"
    },
    {
      "column_count": 17,
      "functional_area": "daily briefs",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "daily_brief"
      ],
      "table": "daily_brief_handoff_lines"
    },
    {
      "column_count": 21,
      "functional_area": "daily briefs",
      "guard_columns": [
        "no_external_assets",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "html_render_receipt_id",
        "content_hash",
        "html_path_redacted",
        "html_path_hash",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "daily_brief",
        "agent_receipts"
      ],
      "table": "daily_brief_html_render_receipts"
    },
    {
      "column_count": 23,
      "functional_area": "daily briefs",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
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
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "daily_brief",
        "automation",
        "agent_receipts"
      ],
      "table": "daily_brief_notification_receipts"
    },
    {
      "column_count": 20,
      "functional_area": "daily briefs",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "daily_brief",
        "agent_receipts"
      ],
      "table": "daily_brief_open_receipts"
    },
    {
      "column_count": 25,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
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
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "daily_brief"
      ],
      "table": "daily_brief_runs"
    },
    {
      "column_count": 8,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [
        "daily_brief"
      ],
      "table": "daily_brief_source_refs"
    },
    {
      "column_count": 9,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "parser_name",
        "content_hash",
        "text_excerpt"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "parser_outputs"
    },
    {
      "column_count": 20,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "second_brain_evaluation_runs"
    },
    {
      "column_count": 30,
      "functional_area": "second-brain retrieval",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "context_quality_class",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "research_packet"
      ],
      "table": "second_brain_research_packets"
    }
  ],
  "raw_prompts_or_responses_exported": false
}
```
