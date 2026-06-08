# 00 Package Manifest

Generated: 2026-06-08T17:15:24.290210+00:00

## Baseline

- Repository: `RMF112018/hb-personal-assistant`
- Package purpose: implementation package for Phase 10A candidate review CLI workflow
- Current audited schema head from repo-truth audit: `V42`
- Target schema head if migration is accepted: `V43`
- Current batch command path observed: `hb-assistant second-brain extract-packets`
- Current single-packet command family observed: `hb-assistant second-brain phase-10 ...`
- Local dirty state: not verified by package generator; local agent must rebaseline.
- Runtime DB state: not verified by package generator; local agent must validate against the populated dev DB.
- Local model runtime: not changed by this package.

## File inventory

- `01_OBJECTIVE_AND_SCOPE.md`
- `02_REPO_TRUTH_AUDIT_BASELINE.md`
- `03_PRODUCT_DECISION_RECORD.md`
- `04_TARGET_CLI_COMMAND_SURFACE.md`
- `05_SCHEMA_AND_MIGRATION_DECISION.md`
- `06_CANDIDATE_REVIEW_DOMAIN_MODEL.md`
- `07_STORE_REPOSITORY_IMPLEMENTATION_PLAN.md`
- `08_CLI_IMPLEMENTATION_PLAN.md`
- `09_REVIEW_ACTION_SEMANTICS.md`
- `10_BATCH_REVIEW_AND_EXPORT_PLAN.md`
- `11_SNOOZE_EDIT_AND_AUDITABILITY_PLAN.md`
- `12_PRIVACY_SECURITY_AND_GUARDRAILS.md`
- `13_TESTING_PLAN.md`
- `14_VALIDATION_AND_EVIDENCE_MATRIX.md`
- `15_MANUAL_DEV_DB_VALIDATION_RUNBOOK.md`
- `16_ROLLBACK_AND_STOP_CONDITIONS.md`
- `17_DO_NOT_OVERCLAIM_REGISTER.md`
- `18_ACCEPTANCE_CHECKLIST.md`
- `19_PROMPT_DEPENDENCY_MAP.md`
- `20_LOCAL_AGENT_EXECUTION_GUIDE.md`
- `21_FINAL_HANDOFF_TEMPLATE.md`
- `README.md`
- `audit_verification/package_generation_summary.json`
- `audit_verification/repo_truth_summary.json`
- `audit_verification/schema_decision_record.json`
- `prompts/Prompt_00_Repo_Truth_Rebaseline.md`
- `prompts/Prompt_01_Schema_V43_Candidate_Review_Migration.md`
- `prompts/Prompt_02_Review_Service_Contracts.md`
- `prompts/Prompt_03_Store_Methods_And_Review_Event_Drift_Fix.md`
- `prompts/Prompt_04_CLI_List_Show_Summary.md`
- `prompts/Prompt_05_CLI_Accept_Ignore_Reject.md`
- `prompts/Prompt_06_CLI_Snooze_Edit_Export_Batch.md`
- `prompts/Prompt_07_Targeted_Service_And_CLI_Tests.md`
- `prompts/Prompt_08_No_Raw_No_Writeback_Proofs.md`
- `prompts/Prompt_09_Docs_Runbooks_And_Evidence.md`
- `prompts/Prompt_10_Final_Validation_Closeout.md`
- `resources/fixtures/local_ai_review/commitment_candidate_pending.json`
- `resources/fixtures/local_ai_review/source_refs_for_candidate.json`
- `resources/fixtures/local_ai_review/task_candidate_pending.json`
- `resources/json/candidate_review_cli_contract.json`
- `resources/json/candidate_review_detail_contract.json`
- `resources/json/candidate_review_event_contract.json`
- `resources/json/candidate_review_list_contract.json`
- `resources/json/candidate_review_summary_contract.json`
- `resources/sql/phase_10a_candidate_review_v43.sql`
- `resources/yaml/phase_10a_candidate_review_policy.seed.yaml`
- `runbooks/phase-10a-candidate-review-cli-runbook.md`
- `runbooks/phase-10a-dev-db-validation-runbook.md`
- `runbooks/phase-10a-final-validation-runbook.md`

## Intended use

Give this complete package to the local coding agent. Execute prompts in numeric order. Repository truth is authoritative over this package.

This package implements a local-only review workflow after Phase 10A candidate extraction. It does not expand extraction scope, change prompts, auto-accept candidates, trigger downstream automations, or perform any external writeback.

## Package posture

The package treats extracted candidates as advisory records requiring human review. The CLI must allow review, correction, suppression, snooze, export, and summary without exposing raw restricted content or mutating Graph, Procore, email, calendar, MCP write paths, or any external system.

## Actual generated file count

50 files.
