# Phase 08B Prompt 07: Job Health, Last-Good-Run, and Observability (Automation Execution Completion Addendum)

**Baseline**: Post-P06 (92- + CLI surfaces + builders for status/diagnostics/last-good-run; executor with 8 stages including job_health_update + closeout, P04 retry/classify metadata in V29 steps, P05 replay link/blocks, P03 apply lock+registry+receipts). No explicit last-good update, job health stage subject to downstream skip on early failure (not guaranteed after all executor outcomes), no last_failed_stage/failure_class/retry_exhausted/catch-up status surfaced in automation status/diagnostics/run/replay/last-good-run payloads or ExecutionResult.

**Objective** (verbatim):
Connect executor outcomes to automation status, job health, diagnostics, and last-good-run tracking.

**Required Work** (verbatim):
1. Update job health after executor runs.
2. Update last-good-run only after full success.
3. Surface last failed stage and failure class.
4. Include retry exhaustion and catch-up status.
5. Include replay eligibility and recovery command.
6. Add tests for success, partial failure, retry exhaustion, and replayable failure.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08b-automation-hardening/last-good-run-proof.json`
- `docs/evidence/construction-intelligence-phase-08b-automation-hardening/daily-brief-job-health-executor-proof.json`

## Design
- **Registry (additive, V29 only)**: `last_good_run(run_kind, db_path)` — returns latest succeeded run row for kind (or None). `update_last_good_run(run_kind, run_registry_id, target_date, db_path)` — records V29 marker step `last_good_run` + `LAST_GOOD_RUN_UPDATED` (the "update" action). Called exclusively from executor success path. Replay/catch-up full successes update last-good for their target date/kind. No schema (no new tables/cols; 151/34 unchanged).
- **Executor (core wiring)**:
  - ExecutionResult extended additively with `last_failed_stage`, `failure_class` (reason_code from first failed StageReceipt/step), `retry_exhausted`, `catch_up`, `replay_run`.
  - In `execute` apply path: track P07 outcome flags on self during fail branches (from classify code + attempt==max for exhaust; is_catchup/replay from plan/req). On full success (`not failed_stage`) after `finish_run`: call `update_last_good_run` (only here).
  - Downstream skip condition changed to exempt `("job_health_update", "closeout")` — health + closeout always dispatch/record even on early failure (update after *all* outcomes).
  - `job_health_update` dispatch: always passes outcome kwargs (`last_failed_stage=..., failure_class=..., retry_exhausted=..., catch_up=..., replay_run=...`). `_default_job_health` filters to canonical args only before forwarding to `run_daily_brief_job_health` (real surface sig unchanged; fakes/proofs receive full outcome for asserts).
  - Dry/blocked paths: P07 fields defaulted (None/False) in result.
  - Recovery rec already carried failed_stage; P07 enriches surfaces downstream.
- **Builders (status/diagnostics, P06 extended)**: After loading steps, derive `last_failed_stage` + `failure_class` (from failed step's reason_code), `retry_exhausted` (heuristic on reason/detail), `catch_up_status` (from step/run reason). Status additionally queries `last_good_run` for inclusion. Payloads preserve all P06 required keys + additive P07 keys + updated guardrails. Read-only paths independent of live executor.
- **CLI (second_brain automation *)**: `last-good-run` now delegates to registry `last_good_run` (thin). All 5 cmds (run/replay/status/diagnostics/last-good-run) include P07 fields in JSON (from result or builders). Base `_AUTOMATION_CLI_GUARDRAILS` extended with P07 attestations. Grammar + --json/--apply --confirm posture unchanged.
- **Exports**: `last_good_run`, `update_last_good_run`, `build_last_good_run_proof`, `build_daily_brief_job_health_executor_proof` (and result fields via ExecutionResult).
- **Tests/Proofs**: Extended `test_automation_executor_service.py` with 4 scenario tests (success updates last_good + marker + health called + surfaces clean; partial: last_good unchanged + last_failed+class surfaced + health called despite skip of prior stages; retry exhaustion: exhausted=true + transient class; replayable: elg true + recovery suggests replay grammar). New proof builders in executor (called by tests) exercise full matrix with fakes (success/partial/exhaust/replayable), pre-pop prior last-good, temp db/locks, ConstructionStore(V34), capture histories/steps/results/payloads, assert side effects (last_good only on full, health calls on fail outcomes, lock release, no raw), write the exact 2 named evidence JSONs with attestations (`fakes_used`, `last_good_updated_only_on_full_success`, `job_health_called_for...`, `schema_version=34`, `lock_released`, `no_raw_content`, `guardrails`, `proof_passed`).
- **No schema / guardrails**: V34/151 literals, table contract untouched. All writes gated (lock+register+steps only on confirmed apply). Fakes + temp only in proofs/tests (never real osascript/vault/HTML/delivery). Dry default, explicit confirm. No raw in any persisted or evidence. Gate remains `deferred_not_blocking` (16/1, covered:true) — "no genuine real apply" per addendum.

## Wiring Summary
- Executor outcome (failed_stage + classify reason_code from P04 + attempt exhaust + catchup/replay flags) → ExecutionResult fields + V29 steps (existing) + `update_last_good_run` (success only) + enriched call to injected job_health (always, via exempt) + builders (steps-derived) + CLI payloads.
- Last-good: only success path marker + query helper.
- Health: guaranteed post-run execution for all outcomes (success/partial/exhaust/replayable); outcome context passed upstream (filtered for real).
- Surfaces (req 3-5): last_failed+class (reason_code), retry_exhausted, catch-up, (replay elg/recovery already from P05/P06, preserved+included).

## Verification
- compileall / ruff / mypy green on touched.
- pytest -m "not live..." (new P07 tests + prior).
- hb construction-agent validate --json (4/4, 34).
- phase-08b-gates (16/1, automation deferred_not_blocking + covered).
- no-writeback / safety / no_raw proofs.
- CLI smokes (all grammar + last-good-run; JSONs contain P06 keys + P07 keys with correct scenario values).
- python -c build_*_proof() writes exact evidence + internal asserts pass.
- Evidence present with required attestations + no raw.
- Arch 93- + 00-README additive.
- git add only P07 files (executor, run_registry, cli/second_brain, __init__, test_..., 93 md, 00-README, 2 evidence); ignore unrelated.

## Evidence Bundle
- last-good-run-proof.json (4 scenarios, last_good side effects, surfaces, health calls, marker steps, attestations).
- daily-brief-job-health-executor-proof.json (health called on success+fail, outcome received on fail, surfaces, attestations).

## Guardrails Preserved
local-first; no external writeback/mutation; no delivery/push; no raw persistence; logs/locks outside repo; dry default + --apply --confirm; no MCP/Llama; additive V29; V34/151; gate deferred (no overstate); fakes in proofs; "ignore unrelated"; only commit summary after land.

## Limitations (per addendum)
- automation_execution gate remains deferred_not_blocking (covered; real scheduled/launchd genuine success not yet — P15 closeout only after).
- job health *compute* (daily_brief_health over daily_brief_runs) unchanged beyond guaranteed post-executor invocation + context kw (connection is orchestration + surfaces).
- No new reason codes (reuse P04 RETRY_* / EXECUTOR_*).

**Per Prompt 07 + P00-P06 baseline + guardrails (additive, repository truth authoritative, do not overstate).**

(End of 93-.)