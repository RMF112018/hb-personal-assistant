# Phase 08B Addendum Prompt 04 — Retry, Backoff, Weekend/Catch-Up, and First-Run-After-Wake (Architecture Note)

**Status**: Implemented (additive to P02 planner + P03 executor). No schema change (V34/151 tables unchanged). Gate `automation_execution` remains `deferred_not_blocking` (requires genuine successful `--apply --confirm` end-to-end before promotion).

## Summary of Changes
- **Failure classification** (in `retry_recovery.py` `classify_execution_failure`): returns `(is_transient_local: bool, reason_code)`. Transient: local DB/IO/lock/timeout/contention (markers). Permanent (never retry): policy/safety/no-input/no-writeback/already-delivered/disabled/hard-fail/external (markers) + conservative default "RETRY_PERMANENT_UNKNOWN".
- **Bounded retry/backoff only for transient**: `AutomationExecutor.execute` (apply+confirm path) loads `phase_08b_retry_backoff_policy.seed.yaml` (max_attempts=3, backoff_seconds=[60,300,900]); per-stage `while attempt <= max: _run_stage; on success record + RETRY_SUCCEEDED; on exc: classify; if not transient or last: mark failed + downstream skip + record RETRY_EXHAUSTED/failed; else evaluate_retry + record RETRY_SCHEDULED + sleep(backoff) + attempt++`. Intermediate transient fails only in `second_brain_retry_receipts` (V30+); final stage outcome in V29 run_steps.
- **Injectable time**: `AutomationExecutor(..., sleep_fn=..., clock=Callable[[], datetime])`; `self._clock`, `self._now()`, `self.now` snapshot at construct. All receipt timestamps and evaluate_retry(..., now=...) use clock in apply path (replaces hard `datetime.now`). Enables deterministic proof sims.
- **Weekend behavior from policy**: `_weekend_catchup_decisions` + new `_is_weekend(dt)` (`.weekday() >= 5`). Only emits `weekend_gate:skip` (WEEKEND_GATE_SKIPPED) on actual Sat/Sun when `weekend_behavior: skip`; on weekdays emits `weekend_gate:proceed` (WEEKDAY_PROCEED). Execute short-circuits on skip decision before lock/stages (all stages recorded `skipped_policy` + reason; finish "skipped").
- **First-run-after-wake catch-up**: Reuses `evaluate_first_run_after_wake` (launchd_scheduler, queries daily_brief_runs + schedule preview; returns needed/stale/not_needed). Decision `catch_up:proceed` (CATCH_UP_NEEDED) on fresh or missed+post-schedule. In execute (post-lock, pre-stages): register_run reason_code=`EXECUTOR_STARTED_CATCHUP`; record_run_step marker `catchup_decision` status=succeeded reason=CATCH_UP_NEEDED (step_order=-1 for visibility). Steps + run receipts persist the signal. (Fixed latent `.get` on model vs dict in decision helper.)
- **Duplicate successful delivery prevention**: In execute apply (after plan, before heavy stages): registry scan via `read_latest_run_registry` (same run_kind + status=succeeded + target_date in started_utc) → `DUPLICATE_SUCCESSFUL_DELIVERY_PREVENTED`; fallback to `evaluate_daily_brief_delivery(written)`. On hit: skip all stages (record `skipped_policy` with reason for each), finish skipped, no fakes/stage work.
- **Metadata receipts**: All paths use existing V29 `register_run` (reason_code carries CATCHUP variant) + `record_run_step` (reason/detail for skips, catchup marker, stage final + retry outcome codes) + `record_retry_attempt` (attempt/backoff/outcome/next_attempt for transient). `StageReceipt` + `ExecutionResult` carry the info; no new columns.
- **Proof builders** (new): `build_retry_backoff_execution_proof`, `build_weekend_catchup_proof`, `build_first_run_after_wake_proof`, `build_duplicate_prevention_proof`. All temp DB/locks, injected 5 fakes (zero real side effects), clock/sleep collectors, pre-pop for dup/catchup, controlled transient raises. Emit attestations (fakes_used, lock_released, no_raw, schema=34, guardrails, specific history e.g. sleep_calls, catchup_steps, dup receipts count).
- **Tests**: Extended `test_automation_executor_service.py` with 4 P04 proof tests (call builders + assert passed + scenario specifics + no raw).
- **Evidence** (exactly 4): `docs/evidence/.../retry-backoff-execution-proof.json`, `weekend-catchup-proof.json`, `first-run-after-wake-proof.json`, `duplicate-prevention-proof.json`.
- **CLI/exports**: No surface change (existing `execute --apply --confirm`, status, plan-execution continue to work; clock/sleep via ctor kwargs in tests). Added exports in `second_brain/__init__.py`.
- **Other**: Updated `ExecutionResult` model Literal to include "skipped" (used by short-circuit paths). `run_automation_execution` passthrough via **kwargs.

## Integration & Guardrails
- Reuses P01 seeds/contracts/reason codes, P02 plan/decisions, P03 lock/registry/stage dispatch + 5 surfaces (faked in proofs/tests), P06 retry_receipts + classify.
- All skip/retry/catchup paths still: acquire lock first, open run, persist steps/receipts, finally release (even on early skip).
- No external writeback/delivery/raw/URLs; dry default; --apply --confirm two-factor; local-only.
- `automation_execution` gate stays deferred_not_blocking (1) per package; proofs attest covered:true but not promoted.
- Architecture 89 (P03) + this 90 additive; 00-README updated.

## Verification Performed
Full matrix (see commit ritual): compileall, ruff check+format, mypy src (255), pytest -m "not live...", `construction-agent validate --json` (4/4, schema 34), `phase-08b-gates` (15/1 with automation deferred), no-writeback-proof, CLI smokes (plan-execution dry, execute dry + blocked confirm, status), 4 new proofs clean.

No overstatement of readiness. Repository truth authoritative.

See package manifest `HB_Construction_Intelligence_Phase_08B_Automation_Execution_Addendum_Package/00_PACKAGE_MANIFEST.md` (Prompt 04) and the 4 evidence JSONs.
