# 00 Package Manifest

Generated: 2026-06-07T19:31:52.391067+00:00

## Package

Phase 10A — Raw Content Enabled Local Intelligence Addendum

## Intent

This is an addendum to Phase 10. It authorizes and specifies raw-content-enabled local intelligence across all local endpoints, starting with email and calendar.

## Execution order

1. Prompt 00 — Rebaseline.
2. Prompt 01 — Config/policy.
3. Prompt 02 — Schema.
4. Prompt 03 — Email raw ingestion.
5. Prompt 04 — Calendar raw ingestion.
6. Prompt 05 — Backend endpoints.
7. Prompt 06 — Raw model context builder.
8. Prompt 07 — Action intelligence extraction.
9. Prompt 08 — Frontend review.
10. Prompt 09 — MCP/Obsidian raw capability.
11. Prompt 10 — Validation closeout.

## Inventory

- `01_OBJECTIVE_AND_SCOPE.md`
- `02_DECISION_RECORD_RAW_CONTENT.md`
- `03_ARCHITECTURE.md`
- `04_SCHEMA_PLAN.md`
- `05_API_ENDPOINT_PLAN.md`
- `06_EMAIL_PLAN.md`
- `07_CALENDAR_PLAN.md`
- `08_MODEL_CONTEXT_PLAN.md`
- `09_OBSIDIAN_AND_MCP_PLAN.md`
- `10_VALIDATION_AND_ACCEPTANCE.md`
- `README.md`
- `evidence_templates/phase_10a_closeout_template.md`
- `prompts/Prompt_00_Raw_Content_Rebaseline.md`
- `prompts/Prompt_01_Config_And_Policy_Surface.md`
- `prompts/Prompt_02_Schema_Additive_Migration.md`
- `prompts/Prompt_03_Email_Raw_Content_Ingestion.md`
- `prompts/Prompt_04_Calendar_Raw_Content_Ingestion.md`
- `prompts/Prompt_05_Backend_Raw_Content_Endpoints.md`
- `prompts/Prompt_06_Raw_Model_Context_Builder.md`
- `prompts/Prompt_07_Action_Intelligence_From_Raw_Content.md`
- `prompts/Prompt_08_Frontend_Raw_Content_Review.md`
- `prompts/Prompt_09_MCP_Obsidian_Raw_Capability.md`
- `prompts/Prompt_10_Validation_Closeout.md`
- `resources/fixtures/raw_calendar/calendar_meeting_prep_packet_001.json`
- `resources/fixtures/raw_email/email_thread_action_packet_001.json`
- `resources/json/calendar_raw_content_packet_schema.json`
- `resources/json/email_raw_content_packet_schema.json`
- `resources/json/raw_action_intelligence_output_schema.json`
- `resources/json/raw_content_api_response_contract.json`
- `resources/json/raw_content_policy_contract.json`
- `resources/sql/phase_10a_raw_content_schema_additions.sql`
- `resources/yaml/phase_10a_raw_content_policy.seed.yaml`
- `runbooks/raw-content-dev-validation-runbook.md`
- `runbooks/raw-model-test-runbook.md`

## Non-negotiable product decision

Raw content is allowed. Metadata-only context is insufficient for the intended assistant capability.
