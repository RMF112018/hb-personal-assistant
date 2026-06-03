# Phase 08B — Prompt 13: Data Quality Gates (verify + document; repo-truth equivalent)

**Status:** Objective **already implemented in repo truth** — verified + documented (additive docs +
one regression test). Schema **V34 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `99ed374` (08B Prompt 12; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-03.

---

## 0. Repo-truth classification (stop-and-report outcome)

The prompt asks to "implement Phase 08B data-quality gates." **They already exist** — built
incrementally across 08B prompts 02–12 and extended throughout this session. Per the standing
guardrail *"Stop and report if repo truth contradicts this prompt"* and the instruction *"document the
repo-truth equivalent,"* this prompt was executed as **verify + document** (operator-confirmed), with
**no redundant runtime gate and no schema change**. The single additive code change is a
coverage-invariant regression test that guards the gates' completeness going forward.

The repo-truth equivalent of "Phase 08B data-quality gates" is:
- `construction/second_brain/data_quality.py::evaluate_phase_08b_data_quality_gates(db_path=…)` +
  `PHASE_08B_GATE_NAMES` (16 entries).
- CLI `hb-assistant second-brain data-quality phase-08b-gates --json`.
- Contract `resources/json/phase_08b_data_quality_gates.json` (`required_fields` ≡ the gate tuple).

---

## 1. Files Changed

- `tests/test_phase_08b_gate_coverage.py` (new) — coverage-invariant meta-gate: every live
  `daily_brief_%_receipts` / `second_brain_%_receipts` table stays in `safety._PHASE_08A_TABLES` (the
  no-writeback live-data scan scope); gate set ≡ contract `required_fields`; fresh-DB gate evaluation
  is fail-free with exactly one deferred surface and not overstated; no-writeback proof passes at
  `LATEST_SCHEMA_VERSION` and covers the four V31–V34 delivery ledgers.
- `docs/architecture/85-phase-08b-data-quality-gates.md` (new) — first single-source description of the
  gate framework (taxonomy, consolidated verdict, invariants, live-data integrity posture, CLI).

**No source / schema / contract / seed change.** Schema **V34 / 151 tables** unchanged.

---

## 2. The 16 gates (repo truth)

| Gate | Kind | Validates |
|---|---|---|
| `agent_run_receipt_persistence` | receipt | V28 agent-run receipt table + guard columns |
| `agent_model_receipt_persistence` | receipt | V28 model-call receipt table + guard columns |
| `delivery_handoff_durability` | receipt | V27 `daily_brief_handoff_lines` durable + guard columns |
| `automation_policy_seed` | policy | 08B automation-policy seed validates against contract |
| `observability_reason_codes` | contract | structured reason-code vocabulary present |
| `automation_health` | proof | P03 read-only runtime health evaluator |
| `launchd_install` | proof | P04 install/uninstall/drift/catch-up (fail-closed, policy-gated) |
| `run_registry_locking` | proof | P05 atomic lock / overlap-block / stale-reclaim / registry |
| `retry_recovery` | proof | P06 retry decision + orphaned-run/stale-lock recovery |
| `freshness_observability` | proof | P07 source/runtime/retrieval freshness |
| `daily_brief_job_health` | proof | P08 job health (healthy/degraded/stale/never-run) |
| `daily_brief_delivery` | proof | P09 idempotent local vault delivery (V31) |
| `daily_brief_html_render` | proof | P10 self-contained HTML + external-asset scan (V32) |
| `daily_brief_notification` | proof | P11 local macOS notification, fail-closed (V33) |
| `daily_brief_open` | proof | P12 brief-open + consolidated status + receipts (V34) |
| `automation_execution` | **deferred** | full executor — `deferred_not_blocking` (never pass) |

Result: **15 pass / 0 warning / 0 fail_blocking / 1 deferred_not_blocking**.

---

## 3. Tests Run

| Command | Result |
|---|---|
| `ruff check tests` (new test) | All checks passed |
| `mypy src` | Success — no issues in **254** source files (unchanged; no `src` change) |
| `pytest tests/test_phase_08b_gate_coverage.py -q` | 4 passed |
| `pytest -m "not integration and not live and not manual"` | **2778 passed, 0 failed, 0 errors** (junit `tests=2778 failures=0 errors=0`) |
| `construction-agent validate --json` | 4/4 passed (schema_version=34, unchanged) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 34 |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **15 pass / 0 warning / 0 fail / 1 deferred**, `required_fields_covered=true`, `readiness_overstated=false` |

---

## 4. Specific Checks → repo-truth evidence

- **Schema version + table lifecycle registrations:** schema **V34 / 151 tables unchanged**; this
  prompt adds no table. Lifecycle contract `table_count` stays 151.
- **CLI dry-run-by-default for apply-capable ops:** the gate evaluator is **read-only** (no
  apply-capable operation to dry-run). The apply-capable 08B surfaces (deliver / render-html / notify
  / open-brief / launchd-install) are each dry-run-by-default + fail-closed, validated by their own
  proof-gates within this set.
- **No external writeback / delivery / raw-content:** `build_second_brain_no_writeback_proof` passes
  at schema 34 — derives guard columns from `_PHASE_08A_TABLES`, scans **live stored rows** for
  secrets/forbidden tokens, scans generated dry-run outputs. FKs are runtime-enforced
  (`PRAGMA foreign_keys = ON`); guard columns + channel/target/mode are `CHECK`-enforced.
- **Actionable reason codes:** each gate carries a structured `reason` (e.g. `RECEIPT_PERSISTENCE_OK`,
  `HEALTH_RETRY_WEEKEND_ALERTING_EXECUTION_DEFERRED`); the contract carries the full reason-code
  vocabulary.
- **success / failure / blocked / stale / dry-run coverage:** exercised by every per-surface
  `build_*_proof` (each drives its surface's success/failure/blocked/stale/dry-run paths on temp DBs),
  the existing `test_phase_08b_data_quality_gates.py` (pass / no-fail / one-deferred / no-overstatement
  / reason codes / no-raw-content), and the new `test_phase_08b_gate_coverage.py` (coverage invariants).

---

## 5. Guardrails Verified

- No schema change; no new runtime gate (avoids duplicating enforced FK/CHECK/no-writeback coverage —
  "no speculative features"). The only code change is a test + docs.
- No external writeback/delivery; no raw-content persisted (the gate evaluator + new test persist
  nothing; the no-writeback proof confirms the live runtime).
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 34.

---

## 6. Known Limitations

1. `automation_execution` stays `deferred_not_blocking` — the lone unbuilt 08B surface (the full
   executor). The gate proof requires ≥ 1 deferred surface, so it is not flipped here.
2. The 08B gate set is intentionally scoped to the `second-brain data-quality phase-08b-gates`
   command; it is not rolled up into the construction-agent top-level surface (operator-confirmed).

---

## 7. Next-Prompt Readiness

The next 08B prompt can safely assume:
- The Phase 08B data-quality gate framework is implemented, **verified** (15 pass / 0 / 0 / 1 deferred,
  `required_fields_covered`, not overstated), now **documented** (architecture 85 + this evidence), and
  **guarded** by `test_phase_08b_gate_coverage.py` against future coverage regressions.
- Full matrix green at schema **V34 / 151 tables**: ruff clean, mypy 254, validate 4/4, pytest 2778
  passed / 0 fail, no-writeback proof at schema 34, phase-08a-gates 8/1/0/3, phase-08b-gates 15/0/0/1.
- The remaining build target is the **full automation executor** — flipping the lone deferred
  `automation_execution` gate.
