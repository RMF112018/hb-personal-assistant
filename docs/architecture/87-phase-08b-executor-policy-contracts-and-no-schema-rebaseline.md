# 87 — Phase 08B: Executor Policy, Contracts & No-Schema Rebaseline (Addendum Prompt 01)

**Phase:** 08B Automation Execution Completion Addendum — Prompt 01
**Schema:** V34 (unchanged); package stays `1.3.0`.
**Status:** Contracts + seeds + loaders + tests only. No executor implementation, no CLI surface, no gate flip, no schema migration. `automation_execution` remains `deferred_not_blocking`.

## Problem

P00 rebaselined that all substrate (run registry V29, retry V30, 4x V31–V34 delivery receipts + 9 guards + lock files + assistant_run_id bridge) exists at V34 and `automation_execution` is the sole deferred gate (reason: HEALTH_RETRY_WEEKEND_ALERTING_EXECUTION_DEFERRED). The declarative policy (sections + reason codes) and contracts for the actual executor (stages, safe replay, weekend/catch-up, execution gate proof shape, validation matrix) were missing. Future executor prompts need this substrate to implement without drift or schema change.

## Design

### 5 new contracts (src/hb_assistant/resources/json/)
- `phase_08b_automation_executor_contract.json` — required_sections (executor, stage_wiring), guardrails (dry_run_default, local_first, idempotent_replay_supported, no_external_*).
- `phase_08b_executor_stage_contract.json` — "stages" dict (preflight/health/weekend/catch/lock/register/core_08a/deliver/render/notify/record/release) + "execution_order" list + per-stage enabled/depends_on/produces.
- `phase_08b_safe_replay_contract.json` — "replay_safety_checks" (lock, run status, delivery status, hash idempotency), "idempotency_keys", blocked_reasons.
- `phase_08b_automation_execution_gate_contract.json` — "required_proof_fields" the eventual executor must satisfy to flip the gate; "expected_deferred", "gate_status_when_complete".
- `phase_08b_executor_validation_matrix.json` — commands (compile/ruff/mypy/pytest -k + hb validates + python load smoke), stop_on.

Registered additively in `contracts.py:PHASE_08B_CONTRACT_FILES` (load_all + set-equality test auto-covers; 08A untouched).

### 4 new policy seeds (resources/config/) + main seed update
Dedicated seeds (loadable via new fns in automation_policy.py):
- `phase_08b_automation_executor_policy.seed.yaml`
- `phase_08b_executor_stage_registry.seed.yaml`
- `phase_08b_retry_backoff_policy.seed.yaml`
- `phase_08b_weekend_catchup_policy.seed.yaml`

Main `phase_08b_automation_policy.seed.yaml` updated additively with high-level `automation_executor` + `executor_stage_registry` sections (before reason_codes) + 18 new reason codes appended to the shared list (EXECUTOR_*/STAGE_*/...).

### Loaders (automation_policy.py)
4 new `load_phase_08b_*_seed()` fns (exact copy of the _load_yaml pattern + existing load fn; ENV_VAR overrides; same error type). Thin; validation left to tests for P01 (future executor will use).

### Tests (only test_phase_08b_contracts_and_seed.py)
- `test_all_08b_contracts_load_with_versions_includes_executor`
- `test_automation_executor_policy_contract_and_seed`
- `test_executor_stage_registry_contract_and_seed`
- `test_retry_backoff_and_weekend_catchup_seeds`
- `test_automation_executor_reason_codes_declared` (new_codes <= seed + policy_contract + gates_contract; validate still valid)

No other 08b tests touched (set-equality and subset checks are additive-safe; gate counts/required_fields untouched).

### No schema bump
Confirmed at runtime (LATEST=34, table_count=151, temp SQLiteMigrator current_version=34, no V35_* in migrator). All executor needs (registry/locks/retry/receipts/guards/bridge) pre-exist since V29–V34. Documented in evidence + this arch.

## Guardrails
Local-first; dry-run default on apply surfaces; no external delivery/writeback; no raw content (hashes/reason codes/statuses only); fail-closed (emit/open flags default false in policy); artifacts (locks, html, receipts) outside repo; reason codes in shared vocab enforced by tests + contracts; `automation_execution` gate stays deferred (do not flip until real impl + proof).

## Known limitations / next
- Executor still not implemented (no run, no wiring to 08A generate + 08B surfaces, no LaunchAgent full path, no last-good-run, no weekend/catchup logic in code).
- `automation_execution` gate + coverage test still expect exactly 1 deferred.
- High-level sections in main seed; details in dedicated seeds (duplication of values acceptable for declarative P01; future can centralize).
- No updates to data_quality.py, PHASE_08B_GATE_NAMES, safety, CLI, or daily_brief_* (per P01 scope).
- Schema blast radius for any future V35 remains (151 literals + lifecycle contract).

## Validation outputs (Prompt 01 run)
| Command | Result |
|---|---|
| `python -m compileall src tests` | 0 |
| `ruff check .` | All checks passed |
| `mypy src` | Success — no issues in 254 source files |
| `pytest -m "not live and not integration and not manual" -k "08b or executor or ...contracts_and_seed"` | 0 failures (new tests pass) |
| `hb-assistant construction-agent validate --json` | 4/4, schema_version=34 |
| `hb-assistant second-brain data-quality phase-08b-gates --json` | 15 pass / 0 / 0 / 1 deferred (`automation_execution` still deferred_not_blocking); required_fields_covered=true; readiness_overstated=false |
| `hb-assistant second-brain data-quality no-writeback-proof --json` | proof_passed=true; no_raw_html_persisted=true; schema 34 |
| python load smoke (5 contracts + 4 seeds) | all load ok; versions phase_08b_*; new codes in vocab; validate still valid |

See `docs/evidence/construction-intelligence-phase-08b-automation-hardening/automation-executor-policy-contract-proof.md` + `.json`.

**Next (per addendum):** Prompt 02+ will implement the executor (consume the loads + contracts + registry/locks/retry, wire stages, safe replay, weekend/catch-up, emit receipts, update gate proof), then final closeout (P15 plan).

No executor behavior, no schema change, no readiness overstatement in this prompt.
