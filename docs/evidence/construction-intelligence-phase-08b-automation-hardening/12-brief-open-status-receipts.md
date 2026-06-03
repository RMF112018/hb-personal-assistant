# Phase 08B — Prompt 12: Brief Open, Delivery Status & Receipts

**Status:** Implemented (additive). Schema **V33 → V34** (one new table); package stays `1.3.0`.
**Baseline:** atop `50222a1` (08B Prompt 11; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-03.
**Scope:** A dry-run-by-default brief-open action (fail-closed `open`), a read-only consolidated
delivery-status, a read-only receipts list, a V34 open-receipt ledger, and a proof-backed
`daily_brief_open` gate. `automation_execution` stays the only deferred 08B gate.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/daily_brief_open.py` (new) — `_default_opener` (macOS
  `open`; injectable), `_policy_open_enabled` (fail-closed gate), `_artifact_present`,
  `evaluate_brief_open`, `run_brief_open_agent` (apply opens + writes V34 receipt; emit-gated V28),
  `write_daily_brief_open_receipt`, `evaluate_brief_delivery_status` (consolidated),
  `list_brief_receipts`, `build_brief_open_proof`.
- `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION 33 → 34`; V34
  `daily_brief_open_receipts` (+ index) with `CHECK(open_target IN ('vault','html'))`, `mode` CHECK,
  `daily_brief_runs` FK, redacted path + path hash, 9 guard columns.
- `src/hb_assistant/construction/second_brain/safety.py` — `daily_brief_open_receipts` added to
  `_PHASE_08A_TABLES`.
- `src/hb_assistant/construction/second_brain/data_quality.py` — `daily_brief_open` proof-gate +
  `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/cli/second_brain.py` — `automation open-brief` (apply-capable, dry-run default),
  `brief-status` (read-only), `receipts` (read-only) commands.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `daily_brief_open` section
  (`open: false` fail-closed default) + reason codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` + `daily_brief_open`.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count 150 → 151` +
  `daily_brief_open_receipts` entry (`v: V34`).

Tests (new): `tests/test_phase_08b_schema_v34.py`, `tests/test_daily_brief_open_agent.py`,
`tests/test_brief_delivery_status_and_receipts.py`, `tests/test_second_brain_open_cli.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (open gate pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership in seed + both contracts);
`contract_table_count` 150 → 151 in nine files (`test_phase_08a_schema_v26.py`,
`test_phase_08b_schema_v28.py … v33.py`, `test_data_quality_table_inventory.py`,
`test_phase_07d_data_quality_gates.py`).

Docs: `docs/architecture/84-phase-08b-brief-open-status-receipts.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **254** source files |
| targeted suite (schema V34 + open agent + status/receipts + CLI + gates + contracts + count bumps) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2774 passed, 0 failed, 0 errors** (junit `tests=2774 failures=0 errors=0`) |
| `construction-agent validate --json` | 4/4 passed (schema_version=34) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 34 (V34 table covered) |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **15 pass / 0 warning / 0 fail / 1 deferred**, `daily_brief_open=pass`, `automation_execution=deferred_not_blocking`, `required_fields_covered=true` |
| `second-brain automation brief-status --json` | reason_code STATUS_NEVER_GENERATED (fresh DB), read-only |
| `second-brain automation receipts --json` | receipt_count 0 (fresh DB), read-only |
| `second-brain automation open-brief --mode dry_run --json` | open_status=preview (no launch) |
| `second-brain automation open-brief --mode apply --json` | opened=false, policy_open_enabled=false (fail-closed) |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V34**; new `daily_brief_open_receipts` ships empty, classified
  `operational_empty_expected` at `table_count` **151**; FK to `daily_brief_runs`; added to
  `safety._PHASE_08A_TABLES`.
- **Dry-run default + fail-closed apply:** `open-brief` defaults to `--mode dry_run` (no `open`); apply
  is real-but-policy-gated — while seed `daily_brief_open.open=false` (default) it returns
  `OPEN_DISABLED_BY_POLICY`, invokes **no** `open` and writes **no** receipt (proven). `brief-status`
  and `receipts` are read-only.
- **Local only / no external delivery / no raw content:** `open_target` is pinned to `vault|html` by a
  DB CHECK (other targets — email/slack/etc — are rejected, proven in
  `test_v34_open_target_is_pinned_to_local_artifacts`). Receipts store only a redacted path + a path
  **hash** (9 guard `CHECK(col = 0)` columns); the consolidated status + receipts list read metadata
  only; `detail`/`path_redacted` validated against forbidden tokens.
- **Actionable reason codes:** `OPEN_NEVER_GENERATED`, `OPEN_BLOCKED`, `OPEN_STALE`,
  `OPEN_NOT_AVAILABLE`, `OPEN_ELIGIBLE`, `OPEN_DISABLED_BY_POLICY`, `OPEN_COMPLETED`,
  `OPEN_ALREADY_OPENED`; consolidated `STATUS_NEVER_GENERATED` / `STATUS_NOT_DELIVERED` /
  `STATUS_DELIVERED` / `STATUS_PARTIAL` / `STATUS_COMPLETE`.
- **Coverage of success / failure / blocked / stale / dry-run:** opened (success); never-generated
  (failure-to-open); blocked run refused (blocked); brief older than threshold (stale); dry-run
  preview launches nothing (dry-run); plus not-available, fail-closed disabled-by-policy, and
  idempotent already-opened; consolidated-status transitions and the receipts list.

---

## 4. Guardrails Verified

- Local-only `open` of the produced artifacts (vault note / `<app_support>/html/`); targets pinned by
  the V34 CHECK; no email/Slack/Teams/SMS/push/webhook/Graph `sendMail`.
- Apply is fail-closed behind `daily_brief_open.open` (default false): never invokes `open` nor writes
  a receipt while disabled (proven via an injected recording opener asserting zero calls). The opener
  is injectable; the suite never launches an app.
- No raw content in receipts (redacted path + path hash only); guard columns enforced at the DB layer
  (nonzero insert raises `IntegrityError`). No external writeback/delivery. Runtime state in SQLite
  outside the repo.
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 34 and now covers `daily_brief_open_receipts`.
- Tests inject a temp app-support DB + a fixed `now` + a fake opener; deterministic.

---

## 5. Known Limitations

1. `automation_execution` stays `deferred_not_blocking` — the final executor + morning-orchestrator
   wiring is unbuilt.
2. Real `open` only fires on a Mac with `daily_brief_open.open=true`; never in the suite. Apply
   persists a V34 receipt only on actual open; the V28 audit receipt is emit-gated. Idempotency keys
   on a prior `opened` receipt for (brief run, target).
3. "Artifact produced" is derived from the V31/V32 terminal receipts (deterministic), not a filesystem
   stat. The per-surface `delivery-status` command from Prompt 09 is unchanged; the consolidated view
   is the new `brief-status`.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V34 / 151 tables**; full matrix green (ruff, mypy 254, validate 4/4, pytest 2774 passed /
  0 fail, no-writeback proof at schema 34, phase-08a-gates 8/1/0/3, phase-08b-gates 15/0/0/1).
- A dry-run-default, idempotent, **local brief-open surface** (V34 `daily_brief_open_receipts`,
  target-pinned to `vault|html`, real-but-policy-gated `open` fail-closed behind
  `daily_brief_open.open`, emit-gated V28 receipt), a read-only **consolidated brief-status**
  (delivered/rendered/notified/opened with `STATUS_*` codes), and a **receipts** list — with a passing
  `daily_brief_open` gate, ready to be wired into the morning orchestrator.
- The remaining build target is the **full automation executor** consuming the 08B observability +
  substrate + delivery + render + notify + open surfaces — flipping the last `deferred_not_blocking`
  gate.
