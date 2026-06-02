# Phase 08B — Prompt 08: Daily Brief Job Health Monitoring

**Status:** Implemented (additive). Schema **V30 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `ed34c64` (08B Prompt 07; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** Read-only, deterministic daily-brief job-health evaluator over the V26 `daily_brief_runs`
ledger + a new proof-backed `daily_brief_job_health` gate. `automation_execution` stays deferred.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/daily_brief_health.py` (new) —
  `evaluate_daily_brief_job_health`, `run_daily_brief_job_health` (V28 emit),
  `build_daily_brief_job_health_proof`.
- `src/hb_assistant/construction/second_brain/data_quality.py` — `daily_brief_job_health`
  proof-gate + `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/cli/second_brain.py` — `automation daily-brief-health` command.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `daily_brief_job_health` section +
  reason codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` +
  `daily_brief_job_health`.

Tests (new): `tests/test_daily_brief_health_agent.py`,
`tests/test_second_brain_daily_brief_health_cli.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (daily_brief_job_health pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership).

Docs: `docs/architecture/80-phase-08b-daily-brief-job-health.md` (new).

**No schema change** — schema V30 / 147 tables unchanged; the receipt reuses the V28
`second_brain_agent_run_receipts` table; no count-literal or lifecycle edits.

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **250** source files |
| targeted suite (daily-brief-health agent + CLI + gates + contracts) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2682 passed, 4 skipped, 1 deselected** (2686 collected; 0 failures, 0 errors; +12 new tests) |
| `construction-agent validate --json` | 4/4 passed (schema_version=30) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 30 |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **11 pass / 0 warning / 0 fail / 1 deferred**, `daily_brief_job_health=pass`, `automation_execution=deferred_not_blocking` |
| `second-brain automation daily-brief-health --json` | reason_code JOB_NEVER_RUN (fresh DB), read-only |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V30 unchanged**; no new table; `table_count` 147 unchanged; the
  receipt reuses the V28 table (already in the no-writeback scan scope).
- **Dry-run default:** the evaluator is read-only; the only apply-capable path is
  `daily-brief-health --emit-receipt`, **off by default**.
- **No writeback / delivery / raw content:** reads only `daily_brief_runs` metadata columns; the V28
  receipt is metadata-only (nine guard `CHECK(col = 0)` columns); proofs scan VALUES not schema names;
  `degradation_mode`/`detail` validated against forbidden tokens.
- **Actionable reason codes:** `JOB_HEALTHY`, `JOB_DEGRADED`, `JOB_STALE`, `JOB_NEVER_RUN`.
- **Coverage of success / failure / blocked / stale / dry-run:** healthy (success); degraded when
  `degradation_mode` set (failure); blocked last run → `JOB_DEGRADED` (blocked); missed cadence →
  `JOB_STALE` (stale); plus `JOB_NEVER_RUN`; read-only with emit off by default (dry-run).

---

## 4. Guardrails Verified

- Read-only evaluator; no external writeback / external delivery; no raw
  email/document/calendar/prompt/response/URL content persisted.
- The emit-gated V28 receipt is metadata-only (guard columns enforced at the DB layer).
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 30.
- Tests use injected temp app-support DB + injected `now`; deterministic.

---

## 5. Known Limitations

1. `automation_execution` stays `deferred_not_blocking` — the final executor consuming all 08B
   observability + substrate surfaces.
2. Health keys off the latest run + a simple consecutive-non-healthy streak; richer rolling SLA
   windows are not yet implemented.
3. A single global `max_age_hours` cadence (per-mode cadence not differentiated).

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V30 / 147 tables** (unchanged); full matrix green (ruff, mypy 250, validate 4/4, pytest
  2682 passed / 4 skipped / 0 fail, no-writeback proof, phase-08a-gates 8/1/0/3, phase-08b-gates
  11/0/0/1).
- A read-only daily-brief job-health surface (healthy / degraded / stale / never-run) with
  structured reason codes and an emit-gated V28 receipt.
- The remaining build target is the **full automation executor** consuming the 08B observability +
  substrate surfaces — flipping the last `deferred_not_blocking` gate.
