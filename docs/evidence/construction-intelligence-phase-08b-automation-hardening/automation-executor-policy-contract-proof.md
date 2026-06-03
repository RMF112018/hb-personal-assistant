# Phase 08B Addendum — Prompt 01: Executor Policy, Contracts, and No-Schema Rebaseline

**Status:** Contracts, seeds, loaders, and tests only (additive). No executor implementation, no new CLI commands, no gate flip, no schema change. `automation_execution` remains the sole `deferred_not_blocking` surface.

**Baseline:** Post-P00 audit at `e2104602d8735cc045119964e3c37fd03e906bd0` (schema V34, table_count 151, package 1.3.0; all substrate pre-exists; 15 pass / 1 deferred on phase-08b-gates).

**Date:** 2026-06-03.

**Package Manifest reference:** HB_Construction_Intelligence_Phase_08B_Automation_Execution_Addendum_Package/00_PACKAGE_MANIFEST.md

**Guardrails:** local-first; no external-system writeback; no email/Slack/... delivery; no raw persistence; logs/locks/artifacts outside repo; dry-run default; apply requires explicit confirmation; no MCP/LlamaIndex.

## Required Work Completed

1. Inspected existing (via grep/runtime/subagent on non-context files + prior P00 audit + patterns from 08a/07d/ retrieval policy + 74/77 arch): main seed has  health_checks/retry/run_recovery/freshness/daily_brief_*/weekend/alerting/launchd/first_run/no_overlap/run_registry + shared reason_codes; automation_policy_contract has base required_sections + full reason_codes + guardrails; data_quality_gates has 16 required_fields (automation_execution deferred) + 83 reason_codes; PHASE_08B_CONTRACT_FILES + loaders; test lockstep.

2. Added/updated contracts (5 new JSON under src/hb_assistant/resources/json/):
   - phase_08b_automation_executor_contract.json
   - phase_08b_executor_stage_contract.json
   - phase_08b_safe_replay_contract.json
   - phase_08b_automation_execution_gate_contract.json
   - phase_08b_executor_validation_matrix.json
   Registered in contracts.py (PHASE_08B_CONTRACT_FILES, 5 new entries with P01 comment). load_all and set-equality now include them.

3. Added/updated policy seeds (4 new YAML under resources/config/ + update to main):
   - phase_08b_automation_executor_policy.seed.yaml
   - phase_08b_executor_stage_registry.seed.yaml
   - phase_08b_retry_backoff_policy.seed.yaml
   - phase_08b_weekend_catchup_policy.seed.yaml
   Main seed: added high-level `automation_executor` + `executor_stage_registry` sections (before reason_codes); appended 18 new codes to reason_codes list.
   (Additive; no removal/dupe of prior P09–P12 sections.)

4. Confirmed no schema bump required (runtime during verif + documented):
   - LATEST_SCHEMA_VERSION still 34.
   - table_lifecycle_status_contract table_count still 151.
   - Temp DB: SQLiteMigrator().apply() on fresh /tmp db yields current_version==34.
   - No V35_STATEMENTS in migrator (grep count 0).
   - Reason (repo truth): executor consumes pre-existing V29–V34 tables (second_brain_run_registry, run_steps, retry_receipts, 4x daily_brief_*_receipts), 9 guards, lock files under app_support, assistant_run_id bridge. P00 temp-migrate + this prompt reconfirm. No new tables/columns/CHECKs.

5. Added tests for contract/policy loaders (only in tests/test_phase_08b_contracts_and_seed.py):
   - test_all_08b_contracts_load_with_versions_includes_executor
   - test_automation_executor_policy_contract_and_seed
   - test_executor_stage_registry_contract_and_seed
   - test_retry_backoff_and_weekend_catchup_seeds
   - test_automation_executor_reason_codes_declared (new_codes <= seed + automation_policy_contract + data_quality_gates_contract; validate still ["valid"]==True)
   All under non-live marker; follow exact prior per-prompt style.

## Files Changed (additive)
- New contracts (5) + registration (contracts.py)
- New seeds (4) + main seed update + new load fns (automation_policy.py)
- Reason code appends only to the two 08b contracts (no required_fields / deferred change)
- New tests (in contracts_and_seed.py)
- New arch 87- + 00-README update
- New evidence (this md + proof.json)

No: migrator, safety, data_quality.py, cli, daily_brief_*.py, table contracts, other tests, other evidence (churn files restored pre-commit if touched).

## Validation (full suite run)
See P01 verification in plan + commit description. All green; phase-08b-gates unchanged (15/1, automation_execution deferred); no-writeback still true; validate 4/4; pytest +new tests 0 fail; loads succeed; no_schema_change true.

## No-Raw / Guardrail Attestation
No raw bodies, prompts, responses, URLs, secrets, or tokens in any new contract/seed/evidence. All are declarative (versions, lists of stages/checks/guardrails, reason code strings, command lists). Proof json + md contain only counts, names, booleans, and the repo sha. DB guards and no-writeback proof scope unchanged.

## Next
Prompts 02+ (per addendum + P00 baseline + P15 plan): implement automation executor (consume the 4 seeds + 5 contracts + registry/locks/retry, run the stage order with safe replay + weekend/catch-up, wire to 08A generate + 08B deliver/render/notify/open, emit V28 receipts, update gate proof to pass, flip when complete). Then final validation closeout + handoff (P15).

**End of Prompt 01 evidence.** Repo truth authoritative.
