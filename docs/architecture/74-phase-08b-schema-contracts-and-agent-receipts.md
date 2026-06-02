# 74 — Phase 08B: Schema, Contracts & Persisted Agent Receipts

**Phase:** 08B (Automation Delivery & Observability) — Prompt 02
**Schema:** V28 (additive; V1–V27 untouched)
**Status:** Implemented. Local-first, read-only against external systems; no external delivery,
metadata-only receipts.

## Problem

Phase 08B needs an observability substrate. Two repo signals pointed here: `reasoning.py`'s
`ModelCallReceipt` was built in memory but never persisted ("deferred to V27"), and the 08A
`model_call_receipt_persistence` gate was `deferred_not_blocking` ("in_memory_only"). There was no
08B contract/seed surface, no structured automation reason-code vocabulary, and no 08B gate report.

## Design

### V28 — persisted agent receipts
Two additive tables (`migrator.py`), each metadata-only with the canonical nine `CHECK(col = 0)`
no-raw/no-writeback guard columns:
- `second_brain_agent_run_receipts` — `agent_run_id` PK, `agent_id`, `run_kind`, `status`,
  `reason_code`, `review_tier` CHECK(1,2,3|null), `degradation_mode`, `model_receipt_count`,
  `started_utc`, `finished_utc`, `created_utc`.
- `second_brain_agent_model_receipts` — `model_receipt_id` PK, `agent_run_id` FK →
  run-receipts `ON DELETE CASCADE`, `model_profile_id`, `model_id`, `input_context_hash`,
  `output_hash`, `input_token_count`, `output_token_count`, `temperature`, `effort`,
  `review_tier_reason_code`, `created_utc`. Content **hashes** + token counts only — never raw
  prompt/response.
Lifecycle contract: `table_count 142 → 144`, both entries `phase_owner: 08B`, `v: V28`,
`operational_empty_expected`.

### Receipt models + writers + wiring
`reasoning.py` gains `AgentRunReceipt` + `build_agent_run_receipt` (and `ModelCallReceipt` now
carries `review_tier_reason_code`); both are `extra="forbid"`. `store.py` gains
`write_agent_run_receipt` / `write_agent_model_receipt` (mirror `write_config_receipt`; guards stay
0). `reasoning.py` stays a pure model boundary — **no DB writes there**. Persistence is wired at the
orchestration site `run_daily_brief`, inside the existing `emit_receipt` block: it records an
agent-run receipt (status/reason-code/tier from the adapter result) + a linked model-call receipt.
Dry-run / `emit_receipt=False` persists nothing.

### 08B contracts + loader + automation policy seed
Three JSON contracts in `resources/json/`: `phase_08b_agent_receipts_contract.json`,
`phase_08b_data_quality_gates.json`, `phase_08b_automation_policy_contract.json`. `contracts.py`
gains `PHASE_08B_CONTRACT_FILES` + `load_phase_08b_contract` / `load_all_phase_08b_contracts`
(08A loader untouched). A YAML policy seed `resources/config/phase_08b_automation_policy.seed.yaml`
declares health-check/retry/weekend posture, **local-only** alerting (external channels forbidden),
and the structured reason-code vocabulary (`HEALTH_CHECK_FAILED`, `RETRY_EXHAUSTED`,
`WEEKEND_GATE_SKIPPED`, `LAUNCHD_NOT_INSTALLED`, `SCHEDULE_DRIFT`, …). `automation_policy.py` loads +
validates it against the contract (mirrors `daily_brief/policy.py`). This is **declarative
substrate** — execution (running checks/retries, real launchd install) is deferred.

### phase-08b-gates
`evaluate_phase_08b_data_quality_gates` (data_quality.py) mirrors the 08A gate report shape +
status vocabulary, with dynamic `LATEST_SCHEMA_VERSION` and `readiness_overstated=False`. Gates:
receipt-persistence (×2) + delivery-handoff durability + automation-policy-seed +
observability-reason-codes = `pass`; automation-execution + launchd-install = `deferred_not_blocking`.
Read-only CLI `second-brain data-quality phase-08b-gates` (exit 0 if ok else 3).

### Mandatory ripple
Persisting the receipt tables required updating the no-writeback proof (`safety.py`): the two tables
moved from the "must-not-exist" `_DEFERRED_RECEIPT_TABLES` (now empty) into `_PHASE_08A_TABLES`, so
they are guard-probed + content-leak-scanned (proven metadata-only, present + guarded). The 08A
`model_call_receipt_persistence` gate stays `deferred_not_blocking` (08A scope) with its reason
updated to point at the V28 persistence assessed in `phase-08b-gates`.

## Guarantees / invariants

- Receipts metadata-only (DB `CHECK(=0)` guards + `extra="forbid"` models + leak scan); no raw
  prompt/response/body/URL/secret.
- No external delivery; alerting policy is `local_only`. Persistence emit-gated (off by default);
  `phase-08b-gates` read-only. Additive migration; runtime artifacts outside the repo.

## Known limitations

- Receipt wiring is on the daily-brief model-call path only; other call sites (interactive query,
  research) can adopt the same emit-gated writers later.
- Automation **execution** (health checks, retries, weekend gating, real launchd install) is
  declared (policy + reason codes) but not executed — deferred to a later 08B prompt
  (`automation_execution` / `launchd_install` gates remain `deferred_not_blocking`).
