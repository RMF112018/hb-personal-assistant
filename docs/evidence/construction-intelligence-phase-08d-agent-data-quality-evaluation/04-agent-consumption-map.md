# 04 Agent Consumption Map

This file is part of an evaluation evidence packet. It records measurable evidence only and does not conclude that the underlying data is usable, meaningful, high quality, or production-ready.

## Machine-Readable Summary

```json
{
  "data_consumer_matrix": [
    {
      "agent_or_workflow": "Deterministic Retrieval Broker",
      "evidence_receipt_tables": [
        "model_call_receipts",
        "agent_run_receipts"
      ],
      "expected_source_families": [
        "email",
        "calendar",
        "documents",
        "Procore",
        "financial",
        "Obsidian"
      ],
      "optional_input_tables": [
        "obsidian_index_entries",
        "research_packets"
      ],
      "output_read_model_tables": [
        "retrieval_context_*",
        "query_tool_receipts"
      ],
      "phase": "08A",
      "required_freshness_fields": [
        "created_at_utc",
        "updated_at_utc",
        "last_seen_utc"
      ],
      "required_input_tables": [
        "retrieval_policy_*",
        "source-linked read models"
      ],
      "required_linkage_fields": [
        "source_id",
        "source_record_id",
        "project_key"
      ],
      "required_review_confidence_fields": [
        "review_required",
        "confidence_label"
      ]
    },
    {
      "agent_or_workflow": "Research Packet Agent",
      "evidence_receipt_tables": [
        "model_call_receipts",
        "agent_run_receipts"
      ],
      "expected_source_families": [
        "approved source-linked local corpus"
      ],
      "optional_input_tables": [
        "obsidian_index_entries",
        "daily_brief_context_items"
      ],
      "output_read_model_tables": [
        "research_packets",
        "research_packet_items"
      ],
      "phase": "08A",
      "required_freshness_fields": [
        "generated_at_utc",
        "source_updated_at_utc"
      ],
      "required_input_tables": [
        "research_packets",
        "retrieval/query read models"
      ],
      "required_linkage_fields": [
        "packet_id",
        "source_id",
        "source_record_id"
      ],
      "required_review_confidence_fields": [
        "context_quality",
        "review_required"
      ]
    },
    {
      "agent_or_workflow": "Output Evaluation Agent",
      "evidence_receipt_tables": [
        "model_call_receipts",
        "agent_run_receipts"
      ],
      "expected_source_families": [
        "generated outputs with source references"
      ],
      "optional_input_tables": [
        "daily_brief_runs",
        "synthesis_outputs"
      ],
      "output_read_model_tables": [
        "generated_output_evaluations"
      ],
      "phase": "08A",
      "required_freshness_fields": [
        "evaluated_at_utc",
        "generated_at_utc"
      ],
      "required_input_tables": [
        "generated_output_evaluations",
        "research_packets"
      ],
      "required_linkage_fields": [
        "output_id",
        "packet_id",
        "source_reference_count"
      ],
      "required_review_confidence_fields": [
        "evaluation_status",
        "review_required",
        "confidence_label"
      ]
    },
    {
      "agent_or_workflow": "Daily Brief Agent",
      "evidence_receipt_tables": [
        "daily_brief_delivery_receipts",
        "brief_open_receipts"
      ],
      "expected_source_families": [
        "calendar",
        "email",
        "documents",
        "Procore",
        "financial",
        "memory"
      ],
      "optional_input_tables": [
        "review_queue",
        "freshness/automation health tables"
      ],
      "output_read_model_tables": [
        "daily_brief_runs",
        "daily_brief_render_views"
      ],
      "phase": "08A/08B",
      "required_freshness_fields": [
        "brief_date",
        "generated_at_utc",
        "source_updated_at_utc"
      ],
      "required_input_tables": [
        "daily_brief_context_items",
        "daily_brief_runs"
      ],
      "required_linkage_fields": [
        "brief_date",
        "source_id",
        "source_record_id",
        "project_key"
      ],
      "required_review_confidence_fields": [
        "review_required",
        "evaluation_status",
        "confidence_label"
      ]
    },
    {
      "agent_or_workflow": "Financial Fact Readiness Agent",
      "evidence_receipt_tables": [
        "financial_review_items",
        "financial_no_writeback_proofs"
      ],
      "expected_source_families": [
        "Procore financial endpoints"
      ],
      "optional_input_tables": [
        "financial_exposure_marts",
        "forecast_readiness_gates"
      ],
      "output_read_model_tables": [
        "financial_exposure_*",
        "forecast_readiness_*"
      ],
      "phase": "08C",
      "required_freshness_fields": [
        "source_updated_at_utc",
        "last_evaluated_utc"
      ],
      "required_input_tables": [
        "financial_amount_facts",
        "financial_source_coverage",
        "financial_review_items"
      ],
      "required_linkage_fields": [
        "project_key",
        "source_family",
        "source_record_id",
        "source_field_path"
      ],
      "required_review_confidence_fields": [
        "review_required",
        "review_tier",
        "confidence_label"
      ]
    },
    {
      "agent_or_workflow": "Review Load / Memory Review Workflows",
      "evidence_receipt_tables": [
        "memory_reviews",
        "operator_feedback"
      ],
      "expected_source_families": [
        "memory",
        "relationship",
        "financial",
        "daily brief",
        "MCP"
      ],
      "optional_input_tables": [
        "operator_preferences",
        "quality_signals"
      ],
      "output_read_model_tables": [
        "review summaries",
        "memory_items"
      ],
      "phase": "08A/08D",
      "required_freshness_fields": [
        "created_at_utc",
        "updated_at_utc"
      ],
      "required_input_tables": [
        "review_queue*",
        "memory_candidates"
      ],
      "required_linkage_fields": [
        "review_item_id",
        "source_id",
        "source_record_id"
      ],
      "required_review_confidence_fields": [
        "review_status",
        "review_tier",
        "confidence_label"
      ]
    },
    {
      "agent_or_workflow": "MCP Tool Broker Agent",
      "evidence_receipt_tables": [
        "mcp_*_receipts",
        "mcp_permission_audit_runs"
      ],
      "expected_source_families": [
        "approved workflow wrappers only"
      ],
      "optional_input_tables": [
        "mcp_resource_registry_snapshots",
        "mcp_prompt_registry_snapshots"
      ],
      "output_read_model_tables": [
        "safe MCP resources/prompts/tools registries"
      ],
      "phase": "08D",
      "required_freshness_fields": [
        "called_at_utc",
        "audited_at_utc",
        "snapshot_at_utc"
      ],
      "required_input_tables": [
        "mcp_tool_call_receipts",
        "mcp_denial_receipts",
        "mcp_permission_audit_runs"
      ],
      "required_linkage_fields": [
        "tool_name",
        "wrapper",
        "receipt_id"
      ],
      "required_review_confidence_fields": [
        "allowed",
        "denial_reason",
        "policy_version"
      ]
    },
    {
      "agent_or_workflow": "Phase 09 Retrieval Readiness Inputs",
      "evidence_receipt_tables": [
        "query_tool_receipts",
        "retrieval broker receipts"
      ],
      "expected_source_families": [
        "approved local corpus behind retrieval broker"
      ],
      "optional_input_tables": [
        "obsidian_index_entries",
        "research_packets",
        "daily_brief_context_items"
      ],
      "output_read_model_tables": [
        "future embeddings/retrieval index"
      ],
      "phase": "09 handoff",
      "required_freshness_fields": [
        "created_at_utc",
        "updated_at_utc",
        "last_seen_utc"
      ],
      "required_input_tables": [
        "source-linked safe read models",
        "retrieval/query receipts"
      ],
      "required_linkage_fields": [
        "source_id",
        "source_record_id",
        "project_key"
      ],
      "required_review_confidence_fields": [
        "review_required",
        "excluded_from_synthesis",
        "confidence_label"
      ]
    }
  ],
  "mapping_is_dependency_evidence_only": true,
  "raw_data_consumed_directly": false
}
```
