# Phase 08B — Prompt 06: Retry/Backoff Receipts & Run Recovery Agent

**Status:** Implemented (additive). Schema **V30** (one new table); package stays `1.3.0`.
**Baseline:** atop `9738393` (08B Prompt 05; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** Deterministic retry/backoff decision + receipts, and a Run Recovery Agent recovering
orphaned runs + stale locks — plus a new proof-backed `retry_recovery` gate. `automation_execution`
(full executor) stays deferred — not overstated.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/retry_recovery.py` (new) — retry/backoff
  (`load_retry_policy`, `plan_retry_schedule`, `evaluate_retry`, `record_retry_attempt`,
  `read_latest_retry_receipts`) + Run Recovery Agent (`evaluate_run_recovery`,
  `run_run_recovery_agent`) + `build_retry_recovery_proof`.
- `src/hb_assistant/construction/second_brain/run_registry.py` — added `clear_stale_lock`
  (removes a stale lock only; never a live one).
- `src/hb_assistant/store/migrator.py` — V30 block (`second_brain_retry_receipts`);
  `LATEST_SCHEMA_VERSION` 29→30.
- `src/hb_assistant/construction/second_brain/data_quality.py` — `retry_recovery` proof-gate +
  `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/construction/second_brain/safety.py` — `second_brain_retry_receipts` added to
  `_PHASE_08A_TABLES`.
- `src/hb_assistant/cli/second_brain.py` — `automation` group: `retry-plan`, `run-recovery`.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `retry` scheduled/succeeded reason
  codes + `run_recovery` section + reason codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` + `retry_recovery`.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count` 146→147 +
  one V30 entry.

Tests (new): `tests/test_retry_recovery_agent.py`, `tests/test_second_brain_retry_recovery_cli.py`,
`tests/test_phase_08b_schema_v30.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (retry_recovery pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership), and the five `146`→`147`
count assertions (`test_data_quality_table_inventory.py`, `test_phase_08a_schema_v26.py`,
`test_phase_07d_data_quality_gates.py`, `test_phase_08b_schema_v28.py`,
`test_phase_08b_schema_v29.py`).

Docs: `docs/architecture/78-phase-08b-retry-backoff-and-run-recovery.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **248** source files |
| targeted suite (retry/recovery agent + CLI + schema v30 + gates + contracts) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2652 passed, 4 skipped, 1 deselected** (2656 collected; 0 failures, 0 errors; +24 new tests) |
| `construction-agent validate --json` | 4/4 passed (schema_version=30) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 30 |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **9 pass / 0 warning / 0 fail / 1 deferred**, `retry_recovery=pass`, `automation_execution=deferred_not_blocking` |
| `second-brain automation retry-plan --json` | max_attempts=3, 3 planned attempts |
| `second-brain automation run-recovery --json` | mode=dry_run, RECOVERY_NOT_NEEDED (fresh DB) |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V30**; one additive table; `table_count` 146→**147**; lifecycle
  + no-writeback scan scope updated; V1-V29 untouched.
- **Dry-run default:** `run-recovery` is `--mode dry_run` by default (no mutation); `retry-plan` is
  read-only.
- **No writeback / delivery / raw content:** retry receipts (V30) + the recovery V28 receipt are
  metadata-only with the nine guard `CHECK(col = 0)` columns; recovery mutates only LOCAL state.
- **Actionable reason codes:** `RETRY_SCHEDULED`, `RETRY_EXHAUSTED`, `RETRY_SUCCEEDED`,
  `RECOVERY_NEEDED`, `RECOVERY_NOT_NEEDED`, `RECOVERY_BLOCKED`, `RUN_ORPHANED`, `RUN_RECOVERED`.
- **Coverage of success / failure / blocked / stale / dry-run:** retry succeeded + recovery
  not-needed (success); retry exhausted (failure); recovery blocked by a live lock (blocked); stale
  lock cleared on recovery (stale); `run-recovery --mode dry_run` does not mutate (dry-run).

---

## 4. Guardrails Verified

- No external writeback / external delivery; no raw email/document/calendar/prompt/response/URL
  content persisted; guard columns enforced at the DB layer; the retry-receipt + recovery proofs
  scan VALUES (not schema field names) for forbidden tokens.
- Recovery is read-only by default; apply mutates only LOCAL registry/lock state.
- `clear_stale_lock` never deletes a live lock (returns `RUN_OVERLAP_BLOCKED`).
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 30 (now covering the V30 table).
- Tests use injected temp app-support / locks dirs + injected `now`; no real lock files touched.

---

## 5. Known Limitations

1. `automation_execution` (weekend execution, local-only alerting emission, full morning-pipeline
   wiring) stays `deferred_not_blocking` — the next/final 08B prompt.
2. Retry is a decision + receipt surface, not a live executor: it does not run/re-run the pipeline;
   `next_attempt_utc` is advisory.
3. Recovery marks orphans `recovered` (a terminal audit state); it does not resume their work.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V30 / 147 tables**; full matrix green (ruff, mypy 248, validate 4/4, pytest 2652
  passed / 4 skipped / 0 fail, no-writeback proof, phase-08a-gates 8/1/0/3, phase-08b-gates 9/0/0/1).
- A deterministic retry/backoff decision + V30 receipt surface and a Run Recovery Agent (dry-run
  default) that recovers orphaned runs + stale locks, plus `clear_stale_lock`.
- The remaining build target is the **full automation executor** (weekend execution + local-only
  alerting + morning-pipeline wiring) consuming retry + recovery + the registry/lock substrate —
  flipping the last `deferred_not_blocking` gate.
