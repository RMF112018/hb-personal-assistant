# Phase 08B — Prompt 05: No-Overlap Locking, Run Registry & Run-Step Ledger

**Status:** Implemented (additive). Schema **V29** (two new tables); package stays `1.3.0`.
**Baseline:** atop `c1eefe8` (08B Prompt 04; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** Durable run-accounting substrate — an atomic no-overlap file lock, a run registry, and a
run-step ledger — plus a new proof-backed `run_registry_locking` data-quality gate.
`automation_execution` (retry/backoff/weekend executor) stays deferred — not overstated.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/run_registry.py` (new) — lock primitives
  (`acquire_run_lock` / `release_run_lock` / `read_run_lock`), registry + step writers/readers,
  `coordinate_no_overlap_run`, `build_run_registry_locking_proof`.
- `src/hb_assistant/store/migrator.py` — V29 block (`second_brain_run_registry` +
  `second_brain_run_steps`); `LATEST_SCHEMA_VERSION` 28→29.
- `src/hb_assistant/config/path_policy.py` — `get_locks_dir()` helper (outside repo; not in
  `ensure_dirs`).
- `src/hb_assistant/construction/second_brain/data_quality.py` — `run_registry_locking` proof-gate
  + `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/construction/second_brain/safety.py` — both tables added to
  `_PHASE_08A_TABLES` (no-writeback scan scope).
- `src/hb_assistant/cli/second_brain.py` — `automation` group: `run-registry-status`,
  `run-lock-status`, `run-lock`.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `no_overlap_locking` + `run_registry`
  sections + reason codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` +
  `run_registry_locking`; `deferred_surfaces` corrected to `["automation_execution"]`.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count` 144→146 +
  two V29 entries.

Tests (new): `tests/test_run_registry_agent.py`, `tests/test_second_brain_run_registry_cli.py`,
`tests/test_phase_08b_schema_v29.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (run_registry_locking pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership), and the four `144`→`146`
count assertions (`test_data_quality_table_inventory.py`, `test_phase_08a_schema_v26.py`,
`test_phase_07d_data_quality_gates.py`, `test_phase_08b_schema_v28.py`).

Docs: `docs/architecture/77-phase-08b-run-registry-and-no-overlap-locking.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **247** source files |
| targeted suite (run-registry agent + CLI + schema v29 + gates + contracts) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2628 passed, 4 skipped, 1 deselected** (2632 collected; 0 failures, 0 errors; +25 new tests) |
| `construction-agent validate --json` | 4/4 passed (schema_version=29) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 29 |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **8 pass / 0 warning / 0 fail / 1 deferred**, `run_registry_locking=pass`, `automation_execution=deferred_not_blocking` |
| `second-brain automation run-registry-status --json` | count=0 (empty; read-only) |
| `second-brain automation run-lock-status --json` | status=absent (read-only) |
| `second-brain automation run-lock --json` | mode=dry_run, acquire.status=preview (no file written) |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V29**; two additive tables; `table_count` 144→**146**; lifecycle
  + no-writeback scan scope updated; V1-V28 untouched.
- **Dry-run default:** `run-lock` is `--mode dry_run` by default (preview, no file); `run-registry-status`
  / `run-lock-status` are read-only.
- **No writeback / delivery / raw content:** registry + step rows are metadata-only with the nine
  guard `CHECK(col = 0)` columns; the prior lock token is **hashed** (never raw) on reclaim; lock
  payloads carry only `{token, run_kind, pid, acquired_utc, expires_after_seconds}`.
- **Actionable reason codes:** `LOCK_ACQUIRED`, `RUN_OVERLAP_BLOCKED`, `STALE_LOCK_RECLAIMED`,
  `LOCK_RELEASED`, `LOCK_RELEASE_TOKEN_MISMATCH`, `RUN_REGISTERED`, `RUN_STEP_RECORDED`.
- **Coverage of success / failure / blocked / stale / dry-run:** acquire success; token-mismatch
  release blocked (failure); concurrent acquire blocked (overlap); stale lock reclaimed; dry-run
  preview — all in `test_run_registry_agent.py`.

---

## 4. Guardrails Verified

- Cross-process exclusion is an **atomic lock file outside the repo** (`<app_support>/locks/`),
  created with `O_CREAT|O_EXCL`; SQLite is not the exclusion mechanism.
- A live lock fails closed (`RUN_OVERLAP_BLOCKED`) with **no deletion**; release requires a matching
  token; a stale lock is reclaimed recording the prior token **hashed**.
- No external writeback / external delivery; no raw email/document/calendar/prompt/response/URL
  content persisted; guard columns enforced at the DB layer.
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 29 (now covering the two V29 tables).
- Tests use injected temp app-support / locks dirs + injected `now`; no real lock files or real
  `launchctl` touched.

---

## 5. Known Limitations

1. `automation_execution` (retry/backoff orchestration, weekend gating, full executor) stays
   `deferred_not_blocking` — the next 08B prompt, which will consume this substrate.
2. The `assistant_run_id` bridge column is present but not yet populated by the legacy
   `MorningRunOrchestrator` (left untouched) — future executor wiring.
3. Lock staleness is time-based (TTL), not PID-liveness probing — sufficient for the single-machine
   launchd + manual-CLI posture.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V29 / 146 tables**; full matrix green (ruff, mypy 247, validate 4/4, pytest 2628
  passed / 4 skipped / 0 fail, no-writeback proof, phase-08a-gates 8/1/0/3, phase-08b-gates 8/0/0/1).
- A durable run-accounting substrate: an atomic no-overlap file lock with stale reclaim +
  token-matched release, an emit-gated V29 run registry (with an `assistant_run_id` bridge), a
  run-step ledger, a coordinator, and a proof-backed `run_registry_locking` gate.
- The remaining build target is the **automation execution layer** (retry/backoff, weekend gating)
  consuming this lock + registry — flipping the last `deferred_not_blocking` gate.
