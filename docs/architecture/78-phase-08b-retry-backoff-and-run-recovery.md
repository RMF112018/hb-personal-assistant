# 78 — Phase 08B: Retry/Backoff Receipts & Run Recovery Agent (Prompt 06)

**Status:** Implemented (additive). Schema **V30** (one new table); package stays `1.3.0`.
**Baseline:** atop `9738393` (08B Prompt 05; 08A closeout `954a518` is ancestor).
**Scope:** Deterministic retry/backoff decision + receipts, and a Run Recovery Agent that recovers
orphaned runs + stale locks — plus a new proof-backed `retry_recovery` gate. The full executor
(weekend execution, alerting delivery, pipeline wiring) stays deferred (`automation_execution`).

## Context

The automation policy already declared a `retry` posture (`max_attempts: 3`,
`backoff_seconds: [60, 300, 900]`, `RETRY_EXHAUSTED`); Prompt 05 added the V29 run registry +
run-step ledger + atomic no-overlap lock. This prompt turns the retry posture into a deterministic
decision + receipt surface and adds the recovery half of the no-overlap story: what happens when a
run is interrupted (a V29 registry row left `started`) and its lock is left behind.

## Design

New module `construction/second_brain/retry_recovery.py`:

- **Retry/backoff (no execution).** `load_retry_policy` reads the seed `retry` block.
  `plan_retry_schedule` returns the read-only `{attempt_number, backoff_seconds}` plan.
  `evaluate_retry(attempt_number, succeeded, now)` decides: succeeded → `RETRY_SUCCEEDED`;
  `attempt_number >= max_attempts` → `RETRY_EXHAUSTED`; else `RETRY_SCHEDULED` with
  `backoff_seconds[attempt_number-1]` and a computed `next_attempt_utc`. `record_retry_attempt`
  persists an emit-gated metadata-only V30 `second_brain_retry_receipts` row.
- **Run Recovery Agent.** `evaluate_run_recovery` (read-only) finds V29 registry rows in the
  orphan status (`started`) and inspects the lock: a live (non-stale) lock → `RECOVERY_BLOCKED`
  (the run may still be active); orphans with no/stale lock → `RECOVERY_NEEDED` (each
  `RUN_ORPHANED`); none → `RECOVERY_NOT_NEEDED`. `run_run_recovery_agent(mode=...)` is **dry-run by
  default**; apply mutates LOCAL state only — `finish_run(status='recovered',
  reason_code=RUN_RECOVERED)` per orphan + clears a stale lock — and emits an optional V28
  `agent_run_receipt` (`agent_id='run_recovery_agent'`).
- **`clear_stale_lock`** added to `run_registry.py` — removes the lock file ONLY if stale
  (`STALE_LOCK_RECLAIMED`); a live lock is left intact (`RUN_OVERLAP_BLOCKED`).
- **`build_retry_recovery_proof()`** drives the gate (temp DB + temp locks dir): retry
  scheduled/exhausted/succeeded reason codes; a guard-zero metadata-only retry receipt; an orphaned
  run recovered end-to-end; values-only no-raw scan (field names legitimately contain `token`).

### Gate / policy / CLI

- `data_quality.py`: new `retry_recovery` proof-gate → **pass**; added to `PHASE_08B_GATE_NAMES` +
  the gates contract `required_fields`. `automation_execution` stays `deferred_not_blocking`.
  phase-08b-gates → **9 pass / 0 warning / 0 fail / 1 deferred**.
- Policy seed: `retry` gains `scheduled_reason_code` + `succeeded_reason_code`; new `run_recovery`
  section (`orphan_status: started` + reason codes). New reason codes mirrored in the
  automation-policy and data-quality-gates contracts.
- CLI `second-brain automation`: `retry-plan` (read-only), `run-recovery --mode dry_run|apply`
  (dry-run default, `--emit-receipt` off by default).

## Guardrails

No external writeback/delivery/raw content; retry receipts (V30) + the recovery V28 receipt are
metadata-only with the nine guard `CHECK(col = 0)` columns. Apply-capable `run-recovery` is dry-run
by default and mutates only LOCAL registry/lock state (never an external system). Schema V1-V29
untouched; `table_count` 146→147; the new table added to the no-writeback scan scope. Lock files
remain outside the repo; a live lock is never deleted.

## Known limitations / next

- `automation_execution` stays deferred — the final executor (weekend execution, local-only
  alerting emission, full morning-pipeline wiring) consuming retry + recovery + registry is the
  next prompt.
- Retry is a **decision + receipt** surface, not a live executor: it does not run or re-run the
  pipeline; `next_attempt_utc` is advisory.
- Recovery marks orphans `recovered` (a terminal audit state); it does not resume their work.
- **Schema blast radius:** a future V31 must update the `147` literals in the five schema/inventory
  tests + the lifecycle `table_count`.
