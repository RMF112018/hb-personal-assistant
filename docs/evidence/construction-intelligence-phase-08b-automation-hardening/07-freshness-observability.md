# Phase 08B — Prompt 07: Source / Runtime / Retrieval Freshness Observability

**Status:** Implemented (additive). Schema **V30 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `1dabcd7` (08B Prompt 06; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** Read-only, deterministic observability — source freshness, runtime health, retrieval
freshness — plus a new proof-backed `freshness_observability` gate. `automation_execution` stays
deferred.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/freshness.py` (new) — `evaluate_source_freshness`,
  `evaluate_retrieval_freshness`, `evaluate_runtime_health` (composes the automation-health agent),
  `evaluate_observability`, `run_observability` (V28 emit), `build_freshness_observability_proof`.
- `src/hb_assistant/construction/second_brain/data_quality.py` — `freshness_observability`
  proof-gate + `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/cli/second_brain.py` — `automation` group: `source-freshness`,
  `retrieval-freshness`, `observability`.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `freshness` section + reason codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` +
  `freshness_observability`.

Tests (new): `tests/test_freshness_observability_agent.py`,
`tests/test_second_brain_observability_cli.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (freshness_observability pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership).

Docs: `docs/architecture/79-phase-08b-freshness-observability.md` (new).

**No schema change** — schema V30 / 147 tables unchanged; the observability receipt reuses the V28
`second_brain_agent_run_receipts` table; no count-literal or lifecycle edits.

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **249** source files |
| targeted suite (freshness agent + CLI + gates + contracts) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2670 passed, 4 skipped, 1 deselected** (2674 collected; 0 failures, 0 errors; +18 new tests) |
| `construction-agent validate --json` | 4/4 passed (schema_version=30) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 30 |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **10 pass / 0 warning / 0 fail / 1 deferred**, `freshness_observability=pass`, `automation_execution=deferred_not_blocking` |
| `second-brain automation source-freshness --json` | per-domain signals + reason codes |
| `second-brain automation retrieval-freshness --json` | index/retrieval signals + reason codes |
| `second-brain automation observability --json` | combined snapshot (source/runtime/retrieval) + reason code |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V30 unchanged**; no new table; `table_count` 147 unchanged; the
  observability receipt reuses the V28 table (already in the no-writeback scan scope).
- **Dry-run default:** all evaluators are read-only; the only apply-capable path is `observability
  --emit-receipt`, **off by default**.
- **No writeback / delivery / raw content:** evaluators are read-only SELECTs; the V28 receipt is
  metadata-only with the nine guard `CHECK(col = 0)` columns; proofs scan VALUES (not schema names).
- **Actionable reason codes:** `SOURCE_FRESH/STALE/UNKNOWN`, `RETRIEVAL_FRESH/STALE/INDEX_MISSING`,
  `RUNTIME_HEALTH_OK/DEGRADED`, `OBSERVABILITY_OK/DEGRADED`.
- **Coverage of success / failure / blocked / stale / dry-run:** all-fresh → OK (success); stale
  source → DEGRADED (failure); explicit source + retrieval stale (stale); unknown source / missing
  index — the read-only analogue of "blocked" (no data to assert on); read-only with emit off by
  default (dry-run).

---

## 4. Guardrails Verified

- All evaluators read-only; no external writeback / external delivery; no raw
  email/document/calendar/prompt/response/URL content persisted.
- The emit-gated V28 receipt is metadata-only (guard columns enforced at the DB layer).
- Runtime health COMPOSES the existing automation-health agent (no duplication, no new checks).
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 30.
- Tests use injected temp app-support DB + injected `now`; deterministic.

---

## 5. Known Limitations

1. `automation_execution` stays `deferred_not_blocking` — the final executor (weekend execution,
   local-only alerting emission, morning-pipeline wiring) is the next/last 08B prompt.
2. Source freshness keys off each domain's *latest* watermark (a coarse roll-up), not per-source-id
   rows.
3. Thresholds are global (per-domain not yet differentiated), defined in the policy seed.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V30 / 147 tables** (unchanged); full matrix green (ruff, mypy 249, validate 4/4, pytest
  2670 passed / 4 skipped / 0 fail, no-writeback proof, phase-08a-gates 8/1/0/3, phase-08b-gates
  10/0/0/1).
- A read-only freshness/health observability surface (source / runtime / retrieval) with structured
  reason codes and an emit-gated V28 receipt, composing the automation-health agent.
- The remaining build target is the **full automation executor** consuming health + freshness +
  retry + recovery + the registry/lock substrate — flipping the last `deferred_not_blocking` gate.
