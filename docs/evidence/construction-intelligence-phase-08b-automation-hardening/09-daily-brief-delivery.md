# Phase 08B — Prompt 09: Daily Brief Delivery Agent (local-only delivery)

**Status:** Implemented (additive). Schema **V30 → V31** (one new table); package stays `1.3.0`.
**Baseline:** atop `aa8886e` (08B Prompt 08; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** A dry-run-by-default Daily Brief Delivery Agent that delivers an approved brief locally to
the Obsidian vault, a V31 delivery-receipt ledger, and a proof-backed `daily_brief_delivery` gate.
`automation_execution` stays the only deferred 08B gate.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/daily_brief_delivery.py` (new) —
  `evaluate_daily_brief_delivery`, `run_daily_brief_delivery_agent` (apply writes the vault note +
  V31 receipt; emit-gated V28 receipt), `write_daily_brief_delivery_receipt`,
  `_render_brief_markdown_from_handoff`, `build_daily_brief_delivery_proof`.
- `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION 30 → 31`; V31
  `daily_brief_delivery_receipts` table (+ index) with `CHECK(delivery_channel = 'obsidian_vault')`,
  `mode` CHECK, `daily_brief_runs` FK, and the 9 no-raw/no-writeback guard columns.
- `src/hb_assistant/construction/second_brain/safety.py` — `daily_brief_delivery_receipts` added to
  `_PHASE_08A_TABLES` (no-writeback scan scope).
- `src/hb_assistant/construction/second_brain/data_quality.py` — `daily_brief_delivery` proof-gate +
  `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/cli/second_brain.py` — `automation delivery-status` (read-only) +
  `automation deliver` (apply-capable, dry-run default) commands.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `daily_brief_delivery` section + reason
  codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` + `daily_brief_delivery`.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count 147 → 148` +
  `daily_brief_delivery_receipts` entry (`v: V31`).

Tests (new): `tests/test_phase_08b_schema_v31.py`, `tests/test_daily_brief_delivery_agent.py`,
`tests/test_second_brain_delivery_cli.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (delivery gate pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership in seed + both contracts);
`table_count` 147 → 148 in `test_data_quality_table_inventory.py`, `test_phase_08a_schema_v26.py`,
`test_phase_07d_data_quality_gates.py`, `test_phase_08b_schema_v28.py`,
`test_phase_08b_schema_v29.py`, `test_phase_08b_schema_v30.py`.

Docs: `docs/architecture/81-phase-08b-daily-brief-delivery.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **251** source files |
| targeted suite (schema V31 + delivery agent + CLI + gates + contracts + count bumps) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2706 passed, 0 failed, 0 errors** (junit `tests=2706 failures=0 errors=0`) |
| `construction-agent validate --json` | 4/4 passed (schema_version=31) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 31 (V31 table covered) |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **12 pass / 0 warning / 0 fail / 1 deferred**, `daily_brief_delivery=pass`, `automation_execution=deferred_not_blocking`, `required_fields_covered=true` |
| `second-brain automation delivery-status --json` | reason_code DELIVERY_NEVER_GENERATED (fresh DB), read-only |
| `second-brain automation deliver --mode dry_run --json` | delivery_status=preview, written=false (writes nothing) |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V31**; new `daily_brief_delivery_receipts` ships empty and is
  classified `operational_empty_expected` at `table_count` **148**; FK to `daily_brief_runs`;
  added to `safety._PHASE_08A_TABLES`.
- **Dry-run default:** `deliver` defaults to `--mode dry_run` (writes nothing); apply is the explicit
  opt-in. `delivery-status` is read-only.
- **No external writeback / delivery / raw content:** the only channel is the Obsidian vault, pinned
  by `CHECK(delivery_channel = 'obsidian_vault')` at the DB layer (external channels — email/slack/
  teams/webhook/graph_sendmail — are rejected, proven in `test_v31_channel_is_pinned_to_obsidian_vault`).
  Receipts are metadata-only (redacted path + content hash + reason code; 9 guard `CHECK(col = 0)`
  columns); the note is rendered from the structured V27 handoff, never a model response;
  `detail`/`degradation_mode`/`output_path_redacted` validated against forbidden tokens; proof scans
  VALUES not schema names.
- **Actionable reason codes:** `DELIVERY_NEVER_GENERATED`, `DELIVERY_BLOCKED`, `DELIVERY_STALE`,
  `DELIVERY_ELIGIBLE`, `DELIVERY_COMPLETED`, `DELIVERY_ALREADY_DELIVERED`.
- **Coverage of success / failure / blocked / stale / dry-run:** completed delivery (success);
  never-generated (failure-to-deliver); blocked run refused (blocked); brief older than threshold
  (stale); dry-run preview writes nothing (dry-run); plus the idempotent already-delivered no-op.

---

## 4. Guardrails Verified

- Local-only delivery; no email/Slack/Teams/SMS/push/webhook/Graph `sendMail` — enforced in code and
  by the V31 channel CHECK.
- Apply writes the redacted, marker-bounded note via the existing `write_brief_output` (atomic) and a
  metadata-only V31 receipt; the V28 agent receipt is emit-gated (off by default). Dry-run writes
  nothing (verified: vault untouched, zero receipts).
- No raw email/document/calendar/prompt/response/URL content persisted; guard columns enforced at the
  DB layer (nonzero insert raises `IntegrityError`).
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 31 and now covers `daily_brief_delivery_receipts`.
- Tests inject a temp app-support DB + temp vault dir + fixed `now`; deterministic; the real Obsidian
  vault is never written by the suite.

---

## 5. Known Limitations

1. `automation_execution` stays `deferred_not_blocking` — the final executor (retry/backoff on a real
   run, weekend gating, local-only alerting emission, morning-orchestrator wiring) is unbuilt.
2. Apply persists the V31 delivery receipt unconditionally (the delivery ledger); the V28 audit
   receipt remains emit-gated. Idempotency keys on a prior `delivered` receipt for the brief run/date.
3. Single global `max_age_hours` (36h); per-mode delivery cadence not differentiated.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V31 / 148 tables**; full matrix green (ruff, mypy 251, validate 4/4, pytest 2706 passed /
  0 fail, no-writeback proof at schema 31, phase-08a-gates 8/1/0/3, phase-08b-gates 12/0/0/1).
- A dry-run-default, idempotent, **local-only Daily Brief Delivery Agent** (V31
  `daily_brief_delivery_receipts`, channel-pinned to the vault, emit-gated V28 receipt) with a passing
  `daily_brief_delivery` gate — ready to be invoked by the morning orchestrator as the delivery step.
- The remaining build target is the **full automation executor** consuming the 08B observability +
  substrate + delivery surfaces — flipping the last `deferred_not_blocking` gate.
