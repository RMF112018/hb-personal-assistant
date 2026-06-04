# 01 Sqlite Structure Inventory

This file is part of an evaluation evidence packet. It records measurable evidence only and does not conclude that the underlying data is usable, meaningful, high quality, or production-ready.

## Machine-Readable Summary

```json
{
  "database_path_redacted": "~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite",
  "empty_tables": [
    "action_items",
    "attachments",
    "calendar_events",
    "construction_data_quality_runs",
    "construction_delta_tokens",
    "construction_document_projection_runs",
    "construction_email_intelligence_deferred_state",
    "construction_file_extraction_runs",
    "construction_graph_download_receipts",
    "construction_graph_link_resolution",
    "construction_project_identity",
    "construction_project_source_matches",
    "construction_source_resolutions",
    "construction_source_sync_state",
    "construction_sync_errors",
    "construction_table_lifecycle_registry",
    "content_embeddings",
    "cross_domain_context_readiness_mart",
    "daily_brief_delivery_receipts",
    "daily_brief_handoff_lines",
    "daily_brief_html_render_receipts",
    "daily_brief_notification_receipts",
    "daily_brief_open_receipts",
    "daily_brief_runs",
    "daily_brief_source_refs",
    "email_intelligence_active_policy",
    "emails",
    "files",
    "interactive_chat_message_receipts",
    "interactive_chat_sessions",
    "launchd_schedule_previews",
    "long_term_memory_items",
    "long_term_memory_quality_signals",
    "long_term_memory_source_refs",
    "memory_update_candidates",
    "memory_update_reviews",
    "obsidian_index_entries",
    "parser_outputs",
    "phase_07d_validation_runs",
    "phase_08a_validation_runs",
    "procore_financial_payment_applications",
    "project_source_coverage_mart",
    "query_tool_receipts",
    "relationship_quality_mart",
    "relationship_resolution_queue",
    "retrieval_context_refs",
    "retrieval_query_receipts",
    "second_brain_agent_model_receipts",
    "second_brain_agent_run_receipts",
    "second_brain_evaluation_runs",
    "second_brain_financial_amount_facts_normalized",
    "second_brain_financial_exposure_summary_items",
    "second_brain_financial_fact_normalization_runs",
    "second_brain_mcp_claude_desktop_config_previews",
    "second_brain_mcp_denial_receipts",
    "second_brain_mcp_permission_audit_runs",
    "second_brain_mcp_policy_gate_runs",
    "second_brain_mcp_prompt_registry_snapshots",
    "second_brain_mcp_resource_registry_snapshots",
    "second_brain_mcp_server_config_snapshots",
    "second_brain_mcp_tool_call_receipts",
    "second_brain_mcp_tool_registry_snapshots",
    "second_brain_operator_feedback",
    "second_brain_operator_preference_profiles",
    "second_brain_phase_08c_validation_runs",
    "second_brain_phase_08d_validation_runs",
    "second_brain_research_packets",
    "second_brain_retry_receipts",
    "second_brain_run_registry",
    "second_brain_run_steps",
    "source_links",
    "source_record_summary_mart",
    "source_records",
    "source_system_record_map",
    "sync_state"
  ],
  "file_size_bytes": 222982144,
  "high_row_count_tables": [
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
      "column_count": 11,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 30822,
      "source_families": [
        "procore"
      ],
      "table": "procore_record_edges"
    },
    {
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "source_url_redacted",
        "raw_body_persisted"
      ],
      "row_count": 30035,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_records"
    },
    {
      "column_count": 21,
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
      "row_count": 27463,
      "source_families": [
        "calendar",
        "procore"
      ],
      "table": "procore_live_record_change_events"
    },
    {
      "column_count": 18,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "text_intelligence_hash",
        "raw_payload_hash",
        "raw_body_persisted"
      ],
      "row_count": 27453,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_record_snapshots"
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
        "current_text_hash",
        "raw_body_persisted"
      ],
      "row_count": 27440,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_record_state_index"
    },
    {
      "column_count": 17,
      "functional_area": "calendar",
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
      "row_count": 27440,
      "source_families": [
        "calendar",
        "procore"
      ],
      "table": "procore_record_timeline_events"
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
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 5836,
      "source_families": [
        "procore"
      ],
      "table": "procore_action_signals"
    },
    {
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "text_intelligence_id",
        "text_hash",
        "text_length",
        "encrypted_full_text_ref",
        "raw_body_persisted"
      ],
      "row_count": 4399,
      "source_families": [
        "procore"
      ],
      "table": "procore_text_intelligence"
    },
    {
      "column_count": 11,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "observation_response_option_ids_json",
        "photo_response_option_ids_json"
      ],
      "row_count": 3484,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_evidence_rules"
    },
    {
      "column_count": 23,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "item_name_redacted",
        "response_id",
        "response_name",
        "response_status"
      ],
      "row_count": 3484,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_items"
    },
    {
      "column_count": 13,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 2220,
      "source_families": [
        "procore"
      ],
      "table": "procore_custom_field_values"
    },
    {
      "column_count": 29,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1880,
      "source_families": [],
      "table": "cross_source_relationship_candidates"
    },
    {
      "column_count": 17,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1880,
      "source_families": [],
      "table": "source_evidence_trails"
    },
    {
      "column_count": 22,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
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
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1780,
      "source_families": [],
      "table": "aging_exposure_report_items"
    },
    {
      "column_count": 27,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1671,
      "source_families": [],
      "table": "cross_source_relationships"
    },
    {
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "attachment_ref_id",
        "procore_attachment_id",
        "filename_redacted",
        "filename_hash",
        "url_hash",
        "url_path_redacted",
        "content_type",
        "download_eligibility",
        "raw_body_persisted"
      ],
      "row_count": 1573,
      "source_families": [
        "procore"
      ],
      "table": "procore_attachment_refs"
    },
    {
      "column_count": 9,
      "functional_area": "validation and data-quality proofs",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "gate_name",
        "raw_body_persisted"
      ],
      "row_count": 1320,
      "source_families": [],
      "table": "data_quality_gate_results"
    },
    {
      "column_count": 7,
      "functional_area": "calendar",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "response_status"
      ],
      "row_count": 1250,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_event_attendees"
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
      "column_count": 9,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "display_name_redacted",
        "address_hash"
      ],
      "row_count": 735,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_message_recipients"
    },
    {
      "column_count": 21,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 598,
      "source_families": [],
      "table": "project_issue_history_items"
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
    }
  ],
  "index_count": 279,
  "last_modified_utc": "2026-06-04T07:26:48.687204+00:00",
  "migration_history": [
    {
      "applied_at": "2026-05-25T09:23:55.285578+00:00",
      "version": 1
    },
    {
      "applied_at": "2026-05-27T12:21:25.455424+00:00",
      "version": 2
    },
    {
      "applied_at": "2026-05-27T13:01:57.594462+00:00",
      "version": 3
    },
    {
      "applied_at": "2026-05-27T13:18:50.251071+00:00",
      "version": 4
    },
    {
      "applied_at": "2026-05-27T16:12:37.839752+00:00",
      "version": 5
    },
    {
      "applied_at": "2026-05-28T16:40:42.787040+00:00",
      "version": 6
    },
    {
      "applied_at": "2026-05-29T13:19:39.101675+00:00",
      "version": 7
    },
    {
      "applied_at": "2026-05-29T20:04:24.968130+00:00",
      "version": 8
    },
    {
      "applied_at": "2026-05-29T20:04:24.968130+00:00",
      "version": 9
    },
    {
      "applied_at": "2026-05-30T06:58:35.019329+00:00",
      "version": 10
    },
    {
      "applied_at": "2026-05-30T06:58:35.019329+00:00",
      "version": 11
    },
    {
      "applied_at": "2026-05-30T08:08:22.450829+00:00",
      "version": 12
    },
    {
      "applied_at": "2026-05-30T09:19:37.960364+00:00",
      "version": 13
    },
    {
      "applied_at": "2026-05-30T10:34:02.888189+00:00",
      "version": 14
    },
    {
      "applied_at": "2026-05-30T12:42:08.825569+00:00",
      "version": 15
    },
    {
      "applied_at": "2026-05-30T13:05:22.815988+00:00",
      "version": 16
    },
    {
      "applied_at": "2026-05-30T14:08:30.760158+00:00",
      "version": 17
    },
    {
      "applied_at": "2026-05-30T15:13:28.872100+00:00",
      "version": 18
    },
    {
      "applied_at": "2026-05-30T15:30:21.137090+00:00",
      "version": 19
    },
    {
      "applied_at": "2026-05-31T09:02:43.080453+00:00",
      "version": 20
    },
    {
      "applied_at": "2026-05-31T09:33:33.898097+00:00",
      "version": 21
    },
    {
      "applied_at": "2026-05-31T10:54:58.381939+00:00",
      "version": 22
    },
    {
      "applied_at": "2026-05-31T11:37:01.122865+00:00",
      "version": 23
    },
    {
      "applied_at": "2026-05-31T19:34:50.012755+00:00",
      "version": 24
    },
    {
      "applied_at": "2026-06-01T09:32:58.312938+00:00",
      "version": 25
    },
    {
      "applied_at": "2026-06-02T08:15:25.231375+00:00",
      "version": 26
    },
    {
      "applied_at": "2026-06-02T19:21:19.845823+00:00",
      "version": 27
    },
    {
      "applied_at": "2026-06-02T19:48:58.326605+00:00",
      "version": 28
    },
    {
      "applied_at": "2026-06-02T21:12:53.357237+00:00",
      "version": 29
    },
    {
      "applied_at": "2026-06-02T21:27:40.227363+00:00",
      "version": 30
    },
    {
      "applied_at": "2026-06-02T22:53:14.647007+00:00",
      "version": 31
    },
    {
      "applied_at": "2026-06-02T23:18:03.080093+00:00",
      "version": 32
    },
    {
      "applied_at": "2026-06-02T23:38:11.255218+00:00",
      "version": 33
    },
    {
      "applied_at": "2026-06-03T06:00:01.314016+00:00",
      "version": 34
    },
    {
      "applied_at": "2026-06-03T13:30:32.215898+00:00",
      "version": 35
    },
    {
      "applied_at": "2026-06-03T17:01:14.754848+00:00",
      "version": 36
    },
    {
      "applied_at": "2026-06-03T21:42:52.027890+00:00",
      "version": 37
    }
  ],
  "read_only_confirmed": true,
  "schema_version_current": 37,
  "schema_version_expected": 37,
  "table_count": 165,
  "table_list": [
    "action_items",
    "aging_exposure_report_items",
    "assistant_runs",
    "attachments",
    "calendar_crawl_runs",
    "calendar_event_attendees",
    "calendar_event_index",
    "calendar_events",
    "calendar_project_match_candidates",
    "calendar_source_locations",
    "calendar_sync_state",
    "construction_crawl_receipts",
    "construction_data_quality_runs",
    "construction_delta_tokens",
    "construction_document_cards",
    "construction_document_classification_candidates",
    "construction_document_intelligence_previews",
    "construction_document_project_match_candidates",
    "construction_document_projection_runs",
    "construction_document_relationship_candidates",
    "construction_drive_item_inventory",
    "construction_drive_items",
    "construction_email_intelligence_deferred_state",
    "construction_file_extraction_runs",
    "construction_file_ingestion_decisions",
    "construction_graph_download_receipts",
    "construction_graph_link_resolution",
    "construction_model_decisions",
    "construction_processing_receipts",
    "construction_project_identity",
    "construction_project_source_matches",
    "construction_review_queue",
    "construction_source_crawl_runs",
    "construction_source_locations",
    "construction_source_resolutions",
    "construction_source_sync_state",
    "construction_sync_errors",
    "construction_table_lifecycle_registry",
    "content_embeddings",
    "cross_domain_context_readiness_mart",
    "cross_source_intelligence_obsidian_runs",
    "cross_source_relationship_candidates",
    "cross_source_relationships",
    "daily_brief_delivery_receipts",
    "daily_brief_handoff_lines",
    "daily_brief_html_render_receipts",
    "daily_brief_notification_receipts",
    "daily_brief_open_receipts",
    "daily_brief_runs",
    "daily_brief_source_refs",
    "data_quality_gate_results",
    "email_crawl_runs",
    "email_intelligence_active_policy",
    "email_message_attachments",
    "email_message_body_vault_refs",
    "email_message_recipients",
    "email_messages",
    "email_model_classifications",
    "email_processing_receipts",
    "email_project_matches",
    "email_relationship_candidates",
    "email_review_queue",
    "email_source_locations",
    "email_sync_state",
    "email_thread_summaries",
    "email_thread_summary_materialization_runs",
    "emails",
    "files",
    "interactive_chat_message_receipts",
    "interactive_chat_sessions",
    "launchd_schedule_previews",
    "long_term_memory_items",
    "long_term_memory_quality_signals",
    "long_term_memory_source_refs",
    "meeting_email_relationship_candidates",
    "meeting_prep_brief_runs",
    "meeting_prep_brief_sections",
    "memory_update_candidates",
    "memory_update_reviews",
    "obsidian_index_entries",
    "obsidian_index_manifests",
    "parser_outputs",
    "phase_07d_validation_runs",
    "phase_08a_validation_runs",
    "procore_action_signals",
    "procore_attachment_refs",
    "procore_company_entities",
    "procore_custom_field_values",
    "procore_financial_amount_facts",
    "procore_financial_billing_periods",
    "procore_financial_budget_changes",
    "procore_financial_budget_rows",
    "procore_financial_budget_views",
    "procore_financial_change_events",
    "procore_financial_change_order_line_items",
    "procore_financial_change_orders",
    "procore_financial_compliance_documents",
    "procore_financial_contracts",
    "procore_financial_invoice_items",
    "procore_financial_line_items",
    "procore_financial_payment_applications",
    "procore_financial_rfqs",
    "procore_financial_subcontractor_invoices",
    "procore_inspection_evidence_rules",
    "procore_inspection_items",
    "procore_inspection_records",
    "procore_inspection_response_options",
    "procore_inspection_response_sets",
    "procore_inspection_sections",
    "procore_live_record_change_events",
    "procore_live_record_snapshots",
    "procore_live_record_state_index",
    "procore_live_records",
    "procore_live_sync_runs",
    "procore_live_sync_watermarks",
    "procore_location_entities",
    "procore_people_entities",
    "procore_record_edges",
    "procore_record_timeline_events",
    "procore_text_intelligence",
    "project_issue_history_items",
    "project_risk_digest_items",
    "project_source_coverage_mart",
    "query_tool_receipts",
    "relationship_quality_mart",
    "relationship_resolution_queue",
    "retrieval_context_refs",
    "retrieval_query_receipts",
    "schema_migrations",
    "second_brain_agent_model_receipts",
    "second_brain_agent_run_receipts",
    "second_brain_evaluation_runs",
    "second_brain_financial_amount_facts_normalized",
    "second_brain_financial_currency_completeness_snapshots",
    "second_brain_financial_exposure_summary_items",
    "second_brain_financial_fact_normalization_runs",
    "second_brain_financial_forecast_readiness_runs",
    "second_brain_financial_readiness_agent_runs",
    "second_brain_financial_review_required_items",
    "second_brain_financial_source_coverage_snapshots",
    "second_brain_financial_wbs_cost_code_snapshots",
    "second_brain_mcp_claude_desktop_config_previews",
    "second_brain_mcp_denial_receipts",
    "second_brain_mcp_permission_audit_runs",
    "second_brain_mcp_policy_gate_runs",
    "second_brain_mcp_prompt_registry_snapshots",
    "second_brain_mcp_resource_registry_snapshots",
    "second_brain_mcp_server_config_snapshots",
    "second_brain_mcp_tool_call_receipts",
    "second_brain_mcp_tool_registry_snapshots",
    "second_brain_operator_feedback",
    "second_brain_operator_preference_profiles",
    "second_brain_phase_08c_validation_runs",
    "second_brain_phase_08d_validation_runs",
    "second_brain_research_packets",
    "second_brain_retry_receipts",
    "second_brain_run_registry",
    "second_brain_run_steps",
    "second_brain_runtime_config_receipts",
    "source_evidence_trails",
    "source_links",
    "source_record_summary_mart",
    "source_records",
    "source_system_record_map",
    "sync_state"
  ],
  "table_summaries": [
    {
      "column_count": 9,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [],
      "table": "action_items"
    },
    {
      "column_count": 22,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
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
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1780,
      "source_families": [],
      "table": "aging_exposure_report_items"
    },
    {
      "column_count": 8,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 47,
      "source_families": [],
      "table": "assistant_runs"
    },
    {
      "column_count": 8,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "attachment_id",
        "name",
        "content_type"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "attachments"
    },
    {
      "column_count": 17,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "row_count": 1,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_crawl_runs"
    },
    {
      "column_count": 7,
      "functional_area": "calendar",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "response_status"
      ],
      "row_count": 1250,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_event_attendees"
    },
    {
      "column_count": 31,
      "functional_area": "calendar",
      "guard_columns": [
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "subject_hash",
        "subject_redacted",
        "subject_token_hashes_json",
        "has_attachments",
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "row_count": 108,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_event_index"
    },
    {
      "column_count": 8,
      "functional_area": "calendar",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_events"
    },
    {
      "column_count": 14,
      "functional_area": "calendar",
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
      "row_count": 8,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_project_match_candidates"
    },
    {
      "column_count": 14,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "calendar_display_name_hash"
      ],
      "row_count": 1,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_source_locations"
    },
    {
      "column_count": 8,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 1,
      "source_families": [
        "calendar"
      ],
      "table": "calendar_sync_state"
    },
    {
      "column_count": 14,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 1,
      "source_families": [
        "agent_receipts"
      ],
      "table": "construction_crawl_receipts"
    },
    {
      "column_count": 10,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "construction_data_quality_runs"
    },
    {
      "column_count": 6,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [],
      "table": "construction_delta_tokens"
    },
    {
      "column_count": 36,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_document_text_persisted",
        "raw_payload_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "source_path_token_hashes_json",
        "raw_document_text_persisted",
        "raw_payload_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 283,
      "source_families": [
        "sharepoint_onedrive"
      ],
      "table": "construction_document_cards"
    },
    {
      "column_count": 15,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_document_text_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "classifier_name",
        "raw_document_text_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 283,
      "source_families": [
        "sharepoint_onedrive"
      ],
      "table": "construction_document_classification_candidates"
    },
    {
      "column_count": 13,
      "functional_area": "review queues",
      "guard_columns": [
        "raw_document_text_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_document_text_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 1,
      "source_families": [
        "sharepoint_onedrive",
        "review_queue"
      ],
      "table": "construction_document_intelligence_previews"
    },
    {
      "column_count": 14,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_document_text_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_document_text_persisted"
      ],
      "row_count": 283,
      "source_families": [
        "sharepoint_onedrive"
      ],
      "table": "construction_document_project_match_candidates"
    },
    {
      "column_count": 10,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_document_text_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_document_text_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "sharepoint_onedrive"
      ],
      "table": "construction_document_projection_runs"
    },
    {
      "column_count": 18,
      "functional_area": "relationship intelligence",
      "guard_columns": [
        "raw_document_text_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_document_text_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 23,
      "source_families": [
        "sharepoint_onedrive"
      ],
      "table": "construction_document_relationship_candidates"
    },
    {
      "column_count": 13,
      "functional_area": "SharePoint / OneDrive",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name",
        "web_url"
      ],
      "row_count": 401,
      "source_families": [
        "microsoft_graph",
        "sharepoint_onedrive"
      ],
      "table": "construction_drive_item_inventory"
    },
    {
      "column_count": 43,
      "functional_area": "SharePoint / OneDrive",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name",
        "web_url"
      ],
      "row_count": 100,
      "source_families": [
        "microsoft_graph",
        "sharepoint_onedrive"
      ],
      "table": "construction_drive_items"
    },
    {
      "column_count": 6,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "persist_full_body"
      ],
      "row_count": 0,
      "source_families": [
        "outlook_email"
      ],
      "table": "construction_email_intelligence_deferred_state"
    },
    {
      "column_count": 15,
      "functional_area": "ingestion state",
      "guard_columns": [
        "full_text_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "parser_name",
        "content_hash",
        "text_excerpt_redacted",
        "full_text_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "sharepoint_onedrive",
        "local_files"
      ],
      "table": "construction_file_extraction_runs"
    },
    {
      "column_count": 14,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "download_allowed"
      ],
      "row_count": 38,
      "source_families": [
        "sharepoint_onedrive",
        "local_files"
      ],
      "table": "construction_file_ingestion_decisions"
    },
    {
      "column_count": 17,
      "functional_area": "Microsoft Graph",
      "guard_columns": [
        "raw_download_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "download_attempted",
        "download_completed",
        "raw_download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "microsoft_graph",
        "agent_receipts"
      ],
      "table": "construction_graph_download_receipts"
    },
    {
      "column_count": 23,
      "functional_area": "Microsoft Graph",
      "guard_columns": [
        "raw_tokenized_url_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "redacted_url",
        "hostname",
        "url_fingerprint",
        "share_token_fingerprint",
        "web_url",
        "name",
        "raw_tokenized_url_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "microsoft_graph"
      ],
      "table": "construction_graph_link_resolution"
    },
    {
      "column_count": 13,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "model_name",
        "raw_output_truncated"
      ],
      "row_count": 3,
      "source_families": [],
      "table": "construction_model_decisions"
    },
    {
      "column_count": 6,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 4,
      "source_families": [
        "agent_receipts"
      ],
      "table": "construction_processing_receipts"
    },
    {
      "column_count": 11,
      "functional_area": "relationship intelligence",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "project_name_raw",
        "project_name_normalized"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "construction_project_identity"
    },
    {
      "column_count": 7,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [],
      "table": "construction_project_source_matches"
    },
    {
      "column_count": 15,
      "functional_area": "review queues",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name"
      ],
      "row_count": 26,
      "source_families": [
        "review_queue"
      ],
      "table": "construction_review_queue"
    },
    {
      "column_count": 13,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 2,
      "source_families": [],
      "table": "construction_source_crawl_runs"
    },
    {
      "column_count": 25,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "source_name",
        "project_name",
        "site_url",
        "folder_web_url",
        "library_name"
      ],
      "row_count": 14,
      "source_families": [],
      "table": "construction_source_locations"
    },
    {
      "column_count": 7,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "web_url"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "construction_source_resolutions"
    },
    {
      "column_count": 11,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [],
      "table": "construction_source_sync_state"
    },
    {
      "column_count": 7,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [],
      "table": "construction_sync_errors"
    },
    {
      "column_count": 9,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "table_name"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "construction_table_lifecycle_registry"
    },
    {
      "column_count": 7,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "content_ref"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "content_embeddings"
    },
    {
      "column_count": 10,
      "functional_area": "second-brain retrieval",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "cross_domain_context_readiness_mart"
    },
    {
      "column_count": 17,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
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
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1,
      "source_families": [
        "obsidian"
      ],
      "table": "cross_source_intelligence_obsidian_runs"
    },
    {
      "column_count": 29,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1880,
      "source_families": [],
      "table": "cross_source_relationship_candidates"
    },
    {
      "column_count": 27,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1671,
      "source_families": [],
      "table": "cross_source_relationships"
    },
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
      "functional_area": "validation and data-quality proofs",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "gate_name",
        "raw_body_persisted"
      ],
      "row_count": 1320,
      "source_families": [],
      "table": "data_quality_gate_results"
    },
    {
      "column_count": 21,
      "functional_area": "ingestion state",
      "guard_columns": [
        "full_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "full_body_persisted",
        "attachment_content_downloaded"
      ],
      "row_count": 18,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_crawl_runs"
    },
    {
      "column_count": 17,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "full_archive_crawl",
        "full_email_body_in_obsidian",
        "attachment_content_download_by_default",
        "ollama_enabled_for_email_intelligence"
      ],
      "row_count": 0,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_intelligence_active_policy"
    },
    {
      "column_count": 15,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "attachment_key",
        "attachment_id",
        "name_redacted",
        "name_hash",
        "content_type",
        "content_downloaded"
      ],
      "row_count": 94,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_message_attachments"
    },
    {
      "column_count": 18,
      "functional_area": "email",
      "guard_columns": [
        "plaintext_persisted",
        "obsidian_body_persisted",
        "evidence_body_persisted",
        "log_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "body_content_type",
        "body_hash",
        "body_length",
        "encrypted_full_body_ref",
        "plaintext_persisted",
        "obsidian_body_persisted",
        "evidence_body_persisted",
        "log_body_persisted"
      ],
      "row_count": 5,
      "source_families": [
        "outlook_email",
        "obsidian"
      ],
      "table": "email_message_body_vault_refs"
    },
    {
      "column_count": 9,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "display_name_redacted",
        "address_hash"
      ],
      "row_count": 735,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_message_recipients"
    },
    {
      "column_count": 36,
      "functional_area": "email",
      "guard_columns": [
        "full_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "folder_display_name",
        "subject_redacted",
        "subject_hash",
        "sender_name_redacted",
        "sender_address_hash",
        "has_attachments",
        "body_preview_hash",
        "body_preview_excerpt_redacted",
        "body_checked",
        "body_mention_detected",
        "full_body_persisted"
      ],
      "row_count": 125,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_messages"
    },
    {
      "column_count": 21,
      "functional_area": "email",
      "guard_columns": [
        "plaintext_body_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "model_name",
        "plaintext_body_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 40,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_model_classifications"
    },
    {
      "column_count": 11,
      "functional_area": "email",
      "guard_columns": [
        "full_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "full_body_persisted",
        "attachment_content_downloaded"
      ],
      "row_count": 14,
      "source_families": [
        "outlook_email",
        "agent_receipts"
      ],
      "table": "email_processing_receipts"
    },
    {
      "column_count": 11,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "project_name_normalized"
      ],
      "row_count": 48,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_project_matches"
    },
    {
      "column_count": 12,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 69,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_relationship_candidates"
    },
    {
      "column_count": 15,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "body_capture_eligible",
        "encrypted_body_capture_allowed",
        "review_required_before_body_use",
        "body_capture_decision_json"
      ],
      "row_count": 22,
      "source_families": [
        "outlook_email",
        "review_queue"
      ],
      "table": "email_review_queue"
    },
    {
      "column_count": 18,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "mailbox_display_name_redacted",
        "mailbox_user_principal_name_hash",
        "folder_display_name",
        "full_archive_crawl_allowed",
        "full_email_body_in_obsidian_allowed"
      ],
      "row_count": 6,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_source_locations"
    },
    {
      "column_count": 12,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "delta_token_fingerprint",
        "delta_token_supported"
      ],
      "row_count": 3,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_sync_state"
    },
    {
      "column_count": 14,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 19,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_thread_summaries"
    },
    {
      "column_count": 14,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_body_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 2,
      "source_families": [
        "outlook_email"
      ],
      "table": "email_thread_summary_materialization_runs"
    },
    {
      "column_count": 11,
      "functional_area": "email",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "has_attachments",
        "body_checked",
        "body_mention_detected"
      ],
      "row_count": 0,
      "source_families": [
        "outlook_email"
      ],
      "table": "emails"
    },
    {
      "column_count": 12,
      "functional_area": "SharePoint / OneDrive",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "name",
        "web_url",
        "download_status"
      ],
      "row_count": 0,
      "source_families": [
        "sharepoint_onedrive"
      ],
      "table": "files"
    },
    {
      "column_count": 10,
      "functional_area": "email",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "model_response_hash",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "outlook_email",
        "agent_receipts"
      ],
      "table": "interactive_chat_message_receipts"
    },
    {
      "column_count": 11,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "interactive_chat_sessions"
    },
    {
      "column_count": 8,
      "functional_area": "review queues",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [
        "review_queue",
        "automation"
      ],
      "table": "launchd_schedule_previews"
    },
    {
      "column_count": 16,
      "functional_area": "memory candidates",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted",
        "retrieved_context_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "memory"
      ],
      "table": "long_term_memory_items"
    },
    {
      "column_count": 13,
      "functional_area": "memory candidates",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "memory"
      ],
      "table": "long_term_memory_quality_signals"
    },
    {
      "column_count": 7,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [
        "memory"
      ],
      "table": "long_term_memory_source_refs"
    },
    {
      "column_count": 20,
      "functional_area": "email",
      "guard_columns": [
        "raw_body_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "subject_topic_signal",
        "raw_body_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 117,
      "source_families": [
        "outlook_email",
        "calendar"
      ],
      "table": "meeting_email_relationship_candidates"
    },
    {
      "column_count": 17,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
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
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1,
      "source_families": [
        "calendar",
        "daily_brief"
      ],
      "table": "meeting_prep_brief_runs"
    },
    {
      "column_count": 17,
      "functional_area": "calendar",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
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
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 8,
      "source_families": [
        "calendar",
        "daily_brief"
      ],
      "table": "meeting_prep_brief_sections"
    },
    {
      "column_count": 16,
      "functional_area": "memory candidates",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "memory"
      ],
      "table": "memory_update_candidates"
    },
    {
      "column_count": 6,
      "functional_area": "review queues",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [
        "review_queue",
        "memory"
      ],
      "table": "memory_update_reviews"
    },
    {
      "column_count": 14,
      "functional_area": "Obsidian integration",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "content_hash"
      ],
      "row_count": 0,
      "source_families": [
        "obsidian"
      ],
      "table": "obsidian_index_entries"
    },
    {
      "column_count": 18,
      "functional_area": "Obsidian integration",
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
      "row_count": 1,
      "source_families": [
        "obsidian"
      ],
      "table": "obsidian_index_manifests"
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
      "column_count": 17,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
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
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "phase_07d_validation_runs"
    },
    {
      "column_count": 11,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "phase_08a_validation_runs"
    },
    {
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 5836,
      "source_families": [
        "procore"
      ],
      "table": "procore_action_signals"
    },
    {
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "attachment_ref_id",
        "procore_attachment_id",
        "filename_redacted",
        "filename_hash",
        "url_hash",
        "url_path_redacted",
        "content_type",
        "download_eligibility",
        "raw_body_persisted"
      ],
      "row_count": 1573,
      "source_families": [
        "procore"
      ],
      "table": "procore_attachment_refs"
    },
    {
      "column_count": 6,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name_redacted"
      ],
      "row_count": 98,
      "source_families": [
        "procore"
      ],
      "table": "procore_company_entities"
    },
    {
      "column_count": 13,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 2220,
      "source_families": [
        "procore"
      ],
      "table": "procore_custom_field_values"
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
      "column_count": 11,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "observation_response_option_ids_json",
        "photo_response_option_ids_json"
      ],
      "row_count": 3484,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_evidence_rules"
    },
    {
      "column_count": 23,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "item_name_redacted",
        "response_id",
        "response_name",
        "response_status"
      ],
      "row_count": 3484,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_items"
    },
    {
      "column_count": 26,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name_redacted",
        "list_template_name_redacted",
        "inspection_type_name"
      ],
      "row_count": 76,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_records"
    },
    {
      "column_count": 7,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "response_option_key",
        "response_set_id",
        "response_option_id",
        "name_redacted"
      ],
      "row_count": 18,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_response_options"
    },
    {
      "column_count": 8,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "response_set_key",
        "response_set_id",
        "name_redacted"
      ],
      "row_count": 6,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_response_sets"
    },
    {
      "column_count": 9,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name_redacted"
      ],
      "row_count": 147,
      "source_families": [
        "procore"
      ],
      "table": "procore_inspection_sections"
    },
    {
      "column_count": 21,
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
      "row_count": 27463,
      "source_families": [
        "calendar",
        "procore"
      ],
      "table": "procore_live_record_change_events"
    },
    {
      "column_count": 18,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "text_intelligence_hash",
        "raw_payload_hash",
        "raw_body_persisted"
      ],
      "row_count": 27453,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_record_snapshots"
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
        "current_text_hash",
        "raw_body_persisted"
      ],
      "row_count": 27440,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_record_state_index"
    },
    {
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "source_url_redacted",
        "raw_body_persisted"
      ],
      "row_count": 30035,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_records"
    },
    {
      "column_count": 21,
      "functional_area": "ingestion state",
      "guard_columns": [
        "raw_body_persisted",
        "no_live_call_performed"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted"
      ],
      "row_count": 508,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_sync_runs"
    },
    {
      "column_count": 7,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 160,
      "source_families": [
        "procore"
      ],
      "table": "procore_live_sync_watermarks"
    },
    {
      "column_count": 9,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name_redacted",
        "node_name_redacted"
      ],
      "row_count": 106,
      "source_families": [
        "procore"
      ],
      "table": "procore_location_entities"
    },
    {
      "column_count": 9,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "display_name_redacted",
        "company_name_redacted",
        "raw_body_persisted"
      ],
      "row_count": 261,
      "source_families": [
        "procore"
      ],
      "table": "procore_people_entities"
    },
    {
      "column_count": 11,
      "functional_area": "Procore",
      "guard_columns": [],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [],
      "row_count": 30822,
      "source_families": [
        "procore"
      ],
      "table": "procore_record_edges"
    },
    {
      "column_count": 17,
      "functional_area": "calendar",
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
      "row_count": 27440,
      "source_families": [
        "calendar",
        "procore"
      ],
      "table": "procore_record_timeline_events"
    },
    {
      "column_count": 17,
      "functional_area": "Procore",
      "guard_columns": [
        "raw_body_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "text_intelligence_id",
        "text_hash",
        "text_length",
        "encrypted_full_text_ref",
        "raw_body_persisted"
      ],
      "row_count": 4399,
      "source_families": [
        "procore"
      ],
      "table": "procore_text_intelligence"
    },
    {
      "column_count": 21,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 598,
      "source_families": [],
      "table": "project_issue_history_items"
    },
    {
      "column_count": 19,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 44,
      "source_families": [],
      "table": "project_risk_digest_items"
    },
    {
      "column_count": 14,
      "functional_area": "source registry",
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
      "row_count": 0,
      "source_families": [],
      "table": "project_source_coverage_mart"
    },
    {
      "column_count": 11,
      "functional_area": "second-brain retrieval",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "tool_name"
      ],
      "row_count": 0,
      "source_families": [
        "mcp",
        "agent_receipts"
      ],
      "table": "query_tool_receipts"
    },
    {
      "column_count": 12,
      "functional_area": "relationship intelligence",
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
      "row_count": 0,
      "source_families": [],
      "table": "relationship_quality_mart"
    },
    {
      "column_count": 17,
      "functional_area": "relationship intelligence",
      "guard_columns": [
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "relationship_resolution_queue"
    },
    {
      "column_count": 10,
      "functional_area": "second-brain retrieval",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [
        "context_ref_id"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "retrieval_context_refs"
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
        "tool_names_json",
        "context_char_count",
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
        "agent_receipts"
      ],
      "table": "retrieval_query_receipts"
    },
    {
      "column_count": 3,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "name"
      ],
      "row_count": 37,
      "source_families": [],
      "table": "schema_migrations"
    },
    {
      "column_count": 21,
      "functional_area": "agent receipts",
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
        "input_context_hash",
        "input_token_count",
        "output_token_count",
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
        "agent_receipts"
      ],
      "table": "second_brain_agent_model_receipts"
    },
    {
      "column_count": 20,
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
        "agent_receipts"
      ],
      "table": "second_brain_agent_run_receipts"
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
    },
    {
      "column_count": 32,
      "functional_area": "review queues",
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
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "client_name",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "review_queue",
        "mcp"
      ],
      "table": "second_brain_mcp_claude_desktop_config_previews"
    },
    {
      "column_count": 30,
      "functional_area": "MCP tools/resources/prompts/receipts",
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
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "client_name",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp",
        "agent_receipts"
      ],
      "table": "second_brain_mcp_denial_receipts"
    },
    {
      "column_count": 28,
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
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
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
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp"
      ],
      "table": "second_brain_mcp_permission_audit_runs"
    },
    {
      "column_count": 28,
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
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
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
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp"
      ],
      "table": "second_brain_mcp_policy_gate_runs"
    },
    {
      "column_count": 26,
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
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "prompt_count",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp"
      ],
      "table": "second_brain_mcp_prompt_registry_snapshots"
    },
    {
      "column_count": 26,
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
      "has_project_entity_reference_fields": false,
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
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp"
      ],
      "table": "second_brain_mcp_resource_registry_snapshots"
    },
    {
      "column_count": 26,
      "functional_area": "MCP tools/resources/prompts/receipts",
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
      "has_project_entity_reference_fields": false,
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
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp"
      ],
      "table": "second_brain_mcp_server_config_snapshots"
    },
    {
      "column_count": 35,
      "functional_area": "MCP tools/resources/prompts/receipts",
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
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "client_name",
        "tool_name",
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_procore_payload_persisted",
        "raw_financial_source_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp",
        "agent_receipts"
      ],
      "table": "second_brain_mcp_tool_call_receipts"
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
      "has_project_entity_reference_fields": false,
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
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [
        "mcp"
      ],
      "table": "second_brain_mcp_tool_registry_snapshots"
    },
    {
      "column_count": 12,
      "functional_area": "unknown / uncategorized",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": false,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "memory"
      ],
      "table": "second_brain_operator_feedback"
    },
    {
      "column_count": 13,
      "functional_area": "SharePoint / OneDrive",
      "guard_columns": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_prompt_persisted",
        "raw_response_persisted"
      ],
      "row_count": 0,
      "source_families": [
        "sharepoint_onedrive",
        "memory"
      ],
      "table": "second_brain_operator_preference_profiles"
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
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
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
      "source_families": [],
      "table": "second_brain_phase_08c_validation_runs"
    },
    {
      "column_count": 31,
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
      "has_json_fields": true,
      "has_project_entity_reference_fields": false,
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
        "download_url_persisted",
        "email_send_performed",
        "raw_store_access_performed"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "second_brain_phase_08d_validation_runs"
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
    },
    {
      "column_count": 19,
      "functional_area": "unknown / uncategorized",
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
        "agent_receipts"
      ],
      "table": "second_brain_retry_receipts"
    },
    {
      "column_count": 21,
      "functional_area": "source registry",
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
        "lock_token",
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
        "automation"
      ],
      "table": "second_brain_run_registry"
    },
    {
      "column_count": 19,
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
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "step_name",
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
      "source_families": [],
      "table": "second_brain_run_steps"
    },
    {
      "column_count": 16,
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
      "row_count": 7,
      "source_families": [
        "agent_receipts"
      ],
      "table": "second_brain_runtime_config_receipts"
    },
    {
      "column_count": 17,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "raw_email_body_persisted",
        "raw_document_text_persisted",
        "raw_calendar_payload_persisted",
        "raw_prompt_persisted",
        "raw_response_persisted",
        "signed_url_persisted",
        "download_url_persisted"
      ],
      "row_count": 1880,
      "source_families": [],
      "table": "source_evidence_trails"
    },
    {
      "column_count": 6,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": false,
      "possible_raw_content_risk_fields": [],
      "row_count": 0,
      "source_families": [],
      "table": "source_links"
    },
    {
      "column_count": 13,
      "functional_area": "source registry",
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
      "source_families": [],
      "table": "source_record_summary_mart"
    },
    {
      "column_count": 13,
      "functional_area": "source registry",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "source_url",
        "content_hash"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "source_records"
    },
    {
      "column_count": 21,
      "functional_area": "source registry",
      "guard_columns": [
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "has_json_fields": true,
      "has_project_entity_reference_fields": true,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "source_url_redacted",
        "raw_body_persisted",
        "full_text_persisted"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "source_system_record_map"
    },
    {
      "column_count": 5,
      "functional_area": "ingestion state",
      "guard_columns": [],
      "has_json_fields": false,
      "has_project_entity_reference_fields": false,
      "has_source_reference_fields": true,
      "has_timestamp_fields": true,
      "possible_raw_content_risk_fields": [
        "source_name"
      ],
      "row_count": 0,
      "source_families": [],
      "table": "sync_state"
    }
  ],
  "tables_grouped_by_functional_area": {
    "MCP tools/resources/prompts/receipts": [
      "second_brain_mcp_denial_receipts",
      "second_brain_mcp_server_config_snapshots",
      "second_brain_mcp_tool_call_receipts"
    ],
    "Microsoft Graph": [
      "construction_graph_download_receipts",
      "construction_graph_link_resolution"
    ],
    "Obsidian integration": [
      "obsidian_index_entries",
      "obsidian_index_manifests"
    ],
    "Procore": [
      "procore_action_signals",
      "procore_attachment_refs",
      "procore_company_entities",
      "procore_custom_field_values",
      "procore_financial_amount_facts",
      "procore_financial_billing_periods",
      "procore_financial_budget_changes",
      "procore_financial_budget_rows",
      "procore_financial_budget_views",
      "procore_financial_change_order_line_items",
      "procore_financial_change_orders",
      "procore_financial_compliance_documents",
      "procore_financial_contracts",
      "procore_financial_invoice_items",
      "procore_financial_line_items",
      "procore_financial_payment_applications",
      "procore_financial_rfqs",
      "procore_financial_subcontractor_invoices",
      "procore_inspection_evidence_rules",
      "procore_inspection_items",
      "procore_inspection_records",
      "procore_inspection_response_options",
      "procore_inspection_response_sets",
      "procore_inspection_sections",
      "procore_live_record_snapshots",
      "procore_live_record_state_index",
      "procore_live_records",
      "procore_location_entities",
      "procore_people_entities",
      "procore_record_edges",
      "procore_text_intelligence"
    ],
    "SharePoint / OneDrive": [
      "construction_drive_item_inventory",
      "construction_drive_items",
      "files",
      "second_brain_operator_preference_profiles"
    ],
    "agent receipts": [
      "second_brain_agent_model_receipts"
    ],
    "calendar": [
      "calendar_event_attendees",
      "calendar_event_index",
      "calendar_events",
      "calendar_project_match_candidates",
      "meeting_prep_brief_sections",
      "procore_financial_change_events",
      "procore_live_record_change_events",
      "procore_record_timeline_events"
    ],
    "daily briefs": [
      "daily_brief_delivery_receipts",
      "daily_brief_handoff_lines",
      "daily_brief_html_render_receipts",
      "daily_brief_notification_receipts",
      "daily_brief_open_receipts"
    ],
    "email": [
      "construction_email_intelligence_deferred_state",
      "email_intelligence_active_policy",
      "email_message_attachments",
      "email_message_body_vault_refs",
      "email_message_recipients",
      "email_messages",
      "email_model_classifications",
      "email_processing_receipts",
      "email_project_matches",
      "email_relationship_candidates",
      "email_review_queue",
      "email_thread_summaries",
      "emails",
      "interactive_chat_message_receipts",
      "meeting_email_relationship_candidates"
    ],
    "financial facts and readiness": [
      "second_brain_financial_amount_facts_normalized",
      "second_brain_financial_currency_completeness_snapshots",
      "second_brain_financial_exposure_summary_items",
      "second_brain_financial_review_required_items",
      "second_brain_financial_wbs_cost_code_snapshots"
    ],
    "ingestion state": [
      "assistant_runs",
      "calendar_crawl_runs",
      "calendar_sync_state",
      "construction_crawl_receipts",
      "construction_data_quality_runs",
      "construction_delta_tokens",
      "construction_document_projection_runs",
      "construction_file_extraction_runs",
      "construction_file_ingestion_decisions",
      "construction_sync_errors",
      "daily_brief_runs",
      "email_crawl_runs",
      "email_sync_state",
      "email_thread_summary_materialization_runs",
      "meeting_prep_brief_runs",
      "phase_07d_validation_runs",
      "phase_08a_validation_runs",
      "procore_live_sync_runs",
      "procore_live_sync_watermarks",
      "second_brain_agent_run_receipts",
      "second_brain_evaluation_runs",
      "second_brain_financial_fact_normalization_runs",
      "second_brain_financial_forecast_readiness_runs",
      "second_brain_financial_readiness_agent_runs",
      "second_brain_mcp_permission_audit_runs",
      "second_brain_mcp_policy_gate_runs",
      "second_brain_phase_08c_validation_runs",
      "second_brain_phase_08d_validation_runs",
      "second_brain_run_steps",
      "second_brain_runtime_config_receipts",
      "sync_state"
    ],
    "memory candidates": [
      "long_term_memory_items",
      "long_term_memory_quality_signals",
      "memory_update_candidates"
    ],
    "relationship intelligence": [
      "construction_document_relationship_candidates",
      "construction_project_identity",
      "relationship_quality_mart",
      "relationship_resolution_queue"
    ],
    "review queues": [
      "construction_document_intelligence_previews",
      "construction_review_queue",
      "launchd_schedule_previews",
      "memory_update_reviews",
      "second_brain_mcp_claude_desktop_config_previews"
    ],
    "second-brain retrieval": [
      "cross_domain_context_readiness_mart",
      "query_tool_receipts",
      "retrieval_context_refs",
      "retrieval_query_receipts",
      "second_brain_research_packets"
    ],
    "source registry": [
      "calendar_source_locations",
      "construction_project_source_matches",
      "construction_source_crawl_runs",
      "construction_source_locations",
      "construction_source_resolutions",
      "construction_source_sync_state",
      "construction_table_lifecycle_registry",
      "cross_source_intelligence_obsidian_runs",
      "cross_source_relationship_candidates",
      "cross_source_relationships",
      "daily_brief_source_refs",
      "email_source_locations",
      "long_term_memory_source_refs",
      "project_source_coverage_mart",
      "second_brain_financial_source_coverage_snapshots",
      "second_brain_mcp_prompt_registry_snapshots",
      "second_brain_mcp_resource_registry_snapshots",
      "second_brain_mcp_tool_registry_snapshots",
      "second_brain_run_registry",
      "source_evidence_trails",
      "source_links",
      "source_record_summary_mart",
      "source_records",
      "source_system_record_map"
    ],
    "unknown / uncategorized": [
      "action_items",
      "aging_exposure_report_items",
      "attachments",
      "construction_document_cards",
      "construction_document_classification_candidates",
      "construction_document_project_match_candidates",
      "construction_model_decisions",
      "construction_processing_receipts",
      "content_embeddings",
      "interactive_chat_sessions",
      "parser_outputs",
      "project_issue_history_items",
      "project_risk_digest_items",
      "schema_migrations",
      "second_brain_operator_feedback",
      "second_brain_retry_receipts"
    ],
    "validation and data-quality proofs": [
      "data_quality_gate_results"
    ]
  },
  "total_row_count": 375853,
  "trigger_count": 0,
  "view_count": 2,
  "view_list": [
    "v_procore_inspection_unanswered_items",
    "v_procore_open_action_signals"
  ]
}
```
