# Phase 08B — Prompt 02: Schema, Contracts, Receipts + phase-08b-gates

**Status:** Implemented (additive). Schema **V27 → V28**; package stays `1.3.0` (repo convention).
**Baseline:** atop `e627bcb` (08B Prompt 01; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** the 08B observability substrate — persisted agent receipt tables + models + writers, 08B
JSON contracts, a YAML automation policy seed with structured reason codes, a `phase-08b-gates`
evaluator/CLI, table-lifecycle registration, and tests. No external delivery; receipts metadata-only.

---

## 1. Files Changed

Source:
- `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION 27→28`; `V28_STATEMENTS`
  (`second_brain_agent_run_receipts` + `second_brain_agent_model_receipts` + indexes); V28 apply block.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count 142→144`;
  two `phase_owner: 08B`, `v: V28` entries.
- `src/hb_assistant/construction/second_brain/reasoning.py` — `AgentRunReceipt` model +
  `build_agent_run_receipt`; `ModelCallReceipt` gains `review_tier_reason_code` (+ docstring: now V28).
- `src/hb_assistant/construction/second_brain/store.py` — `write_agent_run_receipt` /
  `write_agent_model_receipt`.
- `src/hb_assistant/construction/second_brain/daily_brief/generate.py` — capture `resolved_config`;
  persist agent-run + model-call receipts from the existing `emit_receipt` path.
- `src/hb_assistant/resources/json/phase_08b_agent_receipts_contract.json`,
  `phase_08b_data_quality_gates.json`, `phase_08b_automation_policy_contract.json` (new).
- `src/hb_assistant/construction/second_brain/contracts.py` — `PHASE_08B_CONTRACT_FILES` +
  `load_phase_08b_contract` / `load_all_phase_08b_contracts`.
- `resources/config/phase_08b_automation_policy.seed.yaml` (new) +
  `src/hb_assistant/construction/second_brain/automation_policy.py` (loader + validator).
- `src/hb_assistant/construction/second_brain/data_quality.py` —
  `evaluate_phase_08b_data_quality_gates` + `build_phase_08b_gates_proof`; 08A
  `model_call_receipt_persistence` gate reason updated (status unchanged).
- `src/hb_assistant/construction/second_brain/safety.py` — receipt tables added to the guard/leak
  scan scope (`_PHASE_08A_TABLES`); `_DEFERRED_RECEIPT_TABLES` emptied; docstring/comment/stop-condition
  wording updated.
- `src/hb_assistant/cli/second_brain.py` — read-only `data-quality phase-08b-gates` command.

Tests (new): `test_phase_08b_schema_v28.py`, `test_second_brain_agent_receipts.py`,
`test_phase_08b_data_quality_gates.py`, `test_phase_08b_contracts_and_seed.py`.
Tests (updated, count `142→144`): `test_phase_08a_schema_v26.py`,
`test_data_quality_table_inventory.py`, `test_phase_07d_data_quality_gates.py`.

Docs: `docs/architecture/74-phase-08b-schema-contracts-and-agent-receipts.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **244** source files |
| targeted suite (08b schema/receipts/gates/contracts + no-writeback proof + 08a gates + schema/inventory/07d + daily-brief agent) | **89 passed** |
| `pytest -m "not integration and not live and not manual"` | **2575 passed, 1 deselected** (baseline 2553; +22 new) |
| `construction-agent validate --json` | **4/4**, `ok=true` |
| `second-brain data-quality no-writeback-proof --json` | `proof_passed=true`, schema 28 (now scans 21 second-brain tables incl. both receipt tables) |
| `second-brain data-quality phase-08a-gates --json` | **unchanged**: 8 pass / 1 warning / 0 fail_blocking / 3 deferred; `ok=true` |
| `second-brain data-quality phase-08b-gates --json` | 5 pass / 0 warning / 0 fail_blocking / 2 deferred; `ok=true`; `phase_08b_data_quality_gates-v1` |

---

## 3. Specific Checks

- **Schema + lifecycle:** V28; both receipt tables registered `operational_empty_expected`
  (`phase_owner 08B`); migration idempotent; V1–V27 intact.
- **Dry-run default:** receipt persistence is `emit_receipt`-gated (off by default; proven by
  `test_dry_run_no_emit_persists_no_receipts`); `phase-08b-gates` is read-only.
- **No writeback / delivery / raw content:** nine `CHECK(=0)` guard columns per table; model
  receipts store content **hashes** + token counts only; `extra="forbid"` models; no-writeback
  content-leak scan now covers both tables (`proof_passed=true`); automation alerting policy is
  `local_only` (external channels forbidden by contract).
- **Actionable reason codes:** agent-run receipts carry a `reason_code`; the 08B gates emit
  structured reasons (`RECEIPT_PERSISTENCE_OK`, `HEALTH_RETRY_WEEKEND_ALERTING_EXECUTION_DEFERRED`,
  `REAL_LAUNCHD_INSTALL_DEFERRED`); the automation seed declares the
  `HEALTH_CHECK_FAILED`/`RETRY_EXHAUSTED`/`WEEKEND_GATE_SKIPPED`/`LAUNCHD_NOT_INSTALLED`/`SCHEDULE_DRIFT`
  vocabulary.
- **Coverage of success/failure/blocked/stale/dry-run:** writer round-trip + emit success
  (`test_emit_persists_receipts_success`), failure/guard rejection (`test_v28_guard_columns…`,
  `test_v28_review_tier_check_enforced`), blocked (`test_blocked_run_records_receipt_with_reason`),
  stale (`test_stale_run_emits_receipts_no_raw`), dry-run (`test_dry_run_no_emit_persists_no_receipts`).

---

## 4. Guardrails Verified

Local-first; read-only against external systems; no external writeback or delivery
(email/Slack/Teams/SMS/push/webhook/`sendMail` — none); receipts metadata-only (DB CHECKs + model
validators + leak scan); apply-capable persistence dry-run/emit-gated by default; `phase-08b-gates`
read-only; additive migration; runtime artifacts outside the repo. **No repo-truth contradiction;
no stop condition triggered.**

---

## 5. Known Limitations

1. Receipt wiring is on the daily-brief model-call path only; interactive-query / research call
   sites can adopt the same emit-gated writers later.
2. Automation **execution** (health checks, retries, weekend gating, real launchd install) is
   declared (policy + structured reason codes + contract) but not executed — deferred. The
   `automation_execution` and `launchd_install` 08B gates remain `deferred_not_blocking`.
3. The 08A `model_call_receipt_persistence` gate stays `deferred_not_blocking` (08A scope) with an
   updated reason pointing to the V28 persistence assessed in `phase-08b-gates` — the actual
   persisted-receipt readiness is reported by the new 08B gate set.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V28 / 144 tables**; full validation matrix green (ruff, mypy 244, validate 4/4, pytest
  2575, no-writeback-proof, 08A gates unchanged, 08B gates ok).
- Persisted agent receipts (`second_brain_agent_run_receipts` / `second_brain_agent_model_receipts`)
  + writers + emit-gated wiring exist; the 08B contracts (`load_phase_08b_contract`), automation
  policy seed (`validate_phase_08b_automation_policy`), structured reason-code vocabulary, and the
  `phase-08b-gates` evaluator/CLI are in place.
- The **automation execution** layer (run the health-checks/retries/weekend gating using the seeded
  policy + reason codes, real launchd install, run-ledger bridge) is the next build — it consumes
  this substrate and should flip the two deferred 08B gates as it lands. Further persistence stays
  additive (V29+).
