# 00 Package Manifest

Generated: 2026-06-07T18:16:29.167838+00:00

## Baseline

- Repository: `RMF112018/hb-personal-assistant`
- Audited HEAD: `c52cc757b062fe4baf918bd7227dad5e669e3899`
- Package version observed: `1.3.0`
- Frontend version observed: `0.0.0`
- SQLite schema head observed: `V40`
- Local dirty state: not verified by package generator; local agent must rebaseline.
- Target phase: Phase 10 — Local Action Intelligence MVP

## File inventory

- `01_OBJECTIVE_AND_SCOPE.md`
- `02_REPO_TRUTH_AUDIT_BASELINE.md`
- `03_PRODUCT_DECISION_RECORD.md`
- `04_PHASE_10_ARCHITECTURE.md`
- `05_MODEL_RUNTIME_AND_HARDWARE_PLAN.md`
- `06_AUTONOMY_LEVELS_AND_SAFETY.md`
- `07_SCHEMA_AND_MIGRATION_PLAN.md`
- `08_AI_JOB_ORCHESTRATION_PLAN.md`
- `09_TASK_COMMITMENT_EXTRACTION_PLAN.md`
- `10_FOLLOW_UP_MONITOR_PLAN.md`
- `11_RELATIONSHIP_CANDIDATE_ENGINE_PLAN.md`
- `12_DAILY_BRIEF_ACTION_INTELLIGENCE_PLAN.md`
- `13_OBSIDIAN_VAULT_MANAGER_PLAN.md`
- `14_CLAUDE_MCP_CONTEXT_PACKET_PLAN.md`
- `15_FRONTEND_REVIEW_QUEUE_AND_MY_DASHBOARD_PLAN.md`
- `16_EVALUATION_AND_GOLDEN_FIXTURES_PLAN.md`
- `17_PRIVACY_SECURITY_AND_GUARDRAILS.md`
- `18_VALIDATION_AND_EVIDENCE_MATRIX.md`
- `19_IMPLEMENTATION_PHASE_PLAN.md`
- `20_LOCAL_AGENT_EXECUTION_GUIDE.md`
- `21_ROLLBACK_AND_STOP_CONDITIONS.md`
- `22_DEFERRED_SCOPE_AND_FUTURE_PHASES.md`
- `23_DO_NOT_OVERCLAIM_REGISTER.md`
- `24_PHASE_10_EXIT_CRITERIA.md`
- `25_EVIDENCE_TARGETS.md`
- `26_PROMPT_DEPENDENCY_MAP.md`
- `27_PHASE_10_READINESS_ASSESSMENT.md`
- `28_ACCEPTANCE_CHECKLIST.md`
- `README.md`
- `audit_verification/model_runtime_research_summary.json`
- `audit_verification/repo_truth_summary.json`
- `prompts/Prompt_00_Repo_Truth_Audit_And_Phase_10_Rebaseline.md`
- `prompts/Prompt_01_Phase_10_Contracts_Seeds_And_Policy.md`
- `prompts/Prompt_02_Phase_10_Schema_V41_Additive_Migration.md`
- `prompts/Prompt_03_Local_Model_Runtime_Provider_And_Status.md`
- `prompts/Prompt_04_Local_Model_Structured_Output_Client.md`
- `prompts/Prompt_05_AI_Job_Queue_And_Run_Receipts.md`
- `prompts/Prompt_06_Action_Candidate_Output_Contracts_And_Fixture_Runner.md`
- `prompts/Prompt_07_Email_Task_Candidate_Extraction.md`
- `prompts/Prompt_08_Email_Commitment_Candidate_Extraction.md`
- `prompts/Prompt_09_Inbox_Classification_And_Prioritization.md`
- `prompts/Prompt_10_Follow_Up_Watch_Item_Monitor.md`
- `prompts/Prompt_11_Relationship_Candidate_Engine.md`
- `prompts/Prompt_12_Entity_Normalization_And_Deduplication.md`
- `prompts/Prompt_13_Calendar_Intelligence_And_Meeting_Prep_Candidates.md`
- `prompts/Prompt_14_Daily_Brief_Action_Candidates.md`
- `prompts/Prompt_15_Obsidian_Vault_Status_And_Index.md`
- `prompts/Prompt_16_Obsidian_Marker_Bounded_Writer_Expansion.md`
- `prompts/Prompt_17_Obsidian_Tag_And_Organization_Suggestions.md`
- `prompts/Prompt_18_Claude_MCP_Context_Packet_Builder.md`
- `prompts/Prompt_19_MCP_Resources_Tools_And_Prompts.md`
- `prompts/Prompt_20_Backend_API_Action_Intelligence_Surfaces.md`
- `prompts/Prompt_21_Frontend_Navigation_My_Dashboard_And_Today_Nesting.md`
- `prompts/Prompt_22_Frontend_Review_Queue_And_Action_Lanes.md`
- `prompts/Prompt_23_Frontend_Review_Actions_And_Provenance.md`
- `prompts/Prompt_24_Data_Health_Phase_10_Status.md`
- `prompts/Prompt_25_Evaluation_Fixtures_And_Metrics.md`
- `prompts/Prompt_26_No_Raw_No_Writeback_Phase_10_Proofs.md`
- `prompts/Prompt_27_Source_Refresh_Integration_And_Scheduler_Gating.md`
- `prompts/Prompt_28_Dev_Production_Isolation_And_Snapshot_Support.md`
- `prompts/Prompt_29_Operator_Runbooks_And_Copy_Check.md`
- `prompts/Prompt_30_Final_Validation_Closeout_And_Handoff.md`
- `resources/fixtures/local_ai/commitment_candidate_001.json`
- `resources/fixtures/local_ai/email_task_candidate_001.json`
- `resources/fixtures/local_ai/follow_up_monitor_001.json`
- `resources/fixtures/local_ai/relationship_candidate_001.json`
- `resources/fixtures/mcp/daily_brief_packet_001.json`
- `resources/json/phase_10_action_candidate_output_schema.json`
- `resources/json/phase_10_ai_job_contract.json`
- `resources/json/phase_10_claude_mcp_packet_contract.json`
- `resources/json/phase_10_daily_brief_action_candidate_contract.json`
- `resources/json/phase_10_evaluation_metrics_contract.json`
- `resources/json/phase_10_follow_up_watch_contract.json`
- `resources/json/phase_10_frontend_review_queue_contract.json`
- `resources/json/phase_10_local_model_profile_contract.json`
- `resources/json/phase_10_obsidian_vault_manager_contract.json`
- `resources/json/phase_10_relationship_candidate_contract.json`
- `resources/sql/phase_10_schema_additions.sql`
- `resources/yaml/phase_10_ai_job_policy.seed.yaml`
- `resources/yaml/phase_10_local_model_profiles.seed.yaml`
- `resources/yaml/phase_10_mcp_packet_policy.seed.yaml`
- `resources/yaml/phase_10_obsidian_vault_policy.seed.yaml`
- `runbooks/phase-10-action-intelligence-runbook.md`
- `runbooks/phase-10-ai-job-queue-runbook.md`
- `runbooks/phase-10-claude-mcp-packet-runbook.md`
- `runbooks/phase-10-final-validation-runbook.md`
- `runbooks/phase-10-frontend-review-queue-runbook.md`
- `runbooks/phase-10-local-model-runtime-runbook.md`
- `runbooks/phase-10-obsidian-vault-manager-runbook.md`

## Intended use

Give this complete package to the local coding agent. Execute prompts in numeric order. Repository truth is authoritative over this package. Stop on any no-raw/no-writeback, schema validation, source-ref, Obsidian marker-bound, or MCP safety failure.

## Package posture

This package proposes local-only, reviewable, auditable action intelligence. It does not approve or implement external writeback.
