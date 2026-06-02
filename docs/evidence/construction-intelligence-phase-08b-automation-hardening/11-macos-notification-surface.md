# Phase 08B — Prompt 11: macOS Notification Surface

**Status:** Implemented (additive). Schema **V32 → V33** (one new table); package stays `1.3.0`.
**Baseline:** atop `6a89de0` (08B Prompt 10; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** A dry-run-by-default local macOS notification preview/apply surface (fail-closed `osascript`
emission), a V33 notification-receipt ledger, and a proof-backed `daily_brief_notification` gate.
`automation_execution` stays the only deferred 08B gate.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/daily_brief_notify.py` (new) —
  `build_notification_text`, `_default_macos_notifier` (osascript; injectable), `_policy_emit_enabled`
  (fail-closed gate), `evaluate_daily_brief_notification`, `run_daily_brief_notification_agent` (apply
  emits + writes V33 receipt; emit-gated V28 receipt), `write_daily_brief_notification_receipt`,
  `build_daily_brief_notification_proof`.
- `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION 32 → 33`; V33
  `daily_brief_notification_receipts` (+ index) with `CHECK(channel = 'local_macos')`, `mode` CHECK,
  `daily_brief_runs` FK, counts + title hash, 9 no-raw/no-writeback guard columns.
- `src/hb_assistant/construction/second_brain/safety.py` — `daily_brief_notification_receipts` added
  to `_PHASE_08A_TABLES`.
- `src/hb_assistant/construction/second_brain/data_quality.py` — `daily_brief_notification` proof-gate
  + `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/cli/second_brain.py` — `automation notify-status` (read-only) + `notify`
  (apply-capable, dry-run default) commands.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `daily_brief_notification` section
  (`emit: false` fail-closed default) + reason codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` + `daily_brief_notification`.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count 149 → 150` +
  `daily_brief_notification_receipts` entry (`v: V33`).

Tests (new): `tests/test_phase_08b_schema_v33.py`, `tests/test_daily_brief_notify_agent.py`,
`tests/test_second_brain_notify_cli.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (notify gate pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership in seed + both contracts);
`contract_table_count` 149 → 150 in eight files (`test_data_quality_table_inventory.py`,
`test_phase_08a_schema_v26.py`, `test_phase_07d_data_quality_gates.py`, `test_phase_08b_schema_v28.py`,
`test_phase_08b_schema_v29.py`, `test_phase_08b_schema_v30.py`, `test_phase_08b_schema_v31.py`,
`test_phase_08b_schema_v32.py`).

Docs: `docs/architecture/83-phase-08b-macos-notification-surface.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **253** source files |
| targeted suite (schema V33 + notify agent + CLI + gates + contracts + count bumps) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2747 passed, 0 failed, 0 errors** (junit `tests=2747 failures=0 errors=0`) |
| `construction-agent validate --json` | 4/4 passed (schema_version=33) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 33 (V33 table covered) |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **14 pass / 0 warning / 0 fail / 1 deferred**, `daily_brief_notification=pass`, `automation_execution=deferred_not_blocking`, `required_fields_covered=true` |
| `second-brain automation notify-status --json` | reason_code NOTIFY_NEVER_GENERATED (fresh DB), read-only |
| `second-brain automation notify --mode dry_run --json` | notify_status=preview (no emission) |
| `second-brain automation notify --mode apply --json` | emitted=false, policy_emit_enabled=false (fail-closed; no banner) |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V33**; new `daily_brief_notification_receipts` ships empty,
  classified `operational_empty_expected` at `table_count` **150**; FK to `daily_brief_runs`; added to
  `safety._PHASE_08A_TABLES`.
- **Dry-run default + fail-closed apply:** `notify` defaults to `--mode dry_run` (no emission); apply
  is real-but-policy-gated — while seed `daily_brief_notification.emit=false` (default) it returns
  `NOTIFY_DISABLED_BY_POLICY` and invokes **no** `osascript` and writes **no** receipt (proven).
- **Local only / no external delivery / no raw content:** `channel` is pinned to `local_macos` by a DB
  CHECK (external channels — email/slack/teams/push/webhook/local_only — are rejected, proven in
  `test_v33_channel_is_pinned_to_local_macos`). Receipts store only metadata counts + a title **hash**
  (9 guard `CHECK(col = 0)` columns); the raw notification text is never persisted; the banner text is
  built from the structured handoff counts, never a model response; `detail`/`title_preview`/
  `body_preview` validated against forbidden tokens.
- **Actionable reason codes:** `NOTIFY_NEVER_GENERATED`, `NOTIFY_BLOCKED`, `NOTIFY_STALE`,
  `NOTIFY_ELIGIBLE`, `NOTIFY_DISABLED_BY_POLICY`, `NOTIFY_EMITTED`, `NOTIFY_ALREADY_EMITTED`.
- **Coverage of success / failure / blocked / stale / dry-run:** emitted (success); never-generated
  (failure-to-notify); blocked run refused (blocked); brief older than threshold (stale); dry-run
  preview emits nothing (dry-run); plus the fail-closed disabled-by-policy path and the idempotent
  already-emitted no-op.

---

## 4. Guardrails Verified

- Local-only Notification Center banner (the explicit objective) — no email/Slack/Teams/SMS/push/
  webhook/Graph `sendMail`; channel pinned by the V33 CHECK.
- Emission is fail-closed behind `daily_brief_notification.emit` (default false): apply never invokes
  `osascript` nor writes a receipt while disabled (proven via an injected recording notifier asserting
  zero calls). The osascript runner is injectable; the suite never fires a real banner.
- No raw content in receipts (counts + title hash only); guard columns enforced at the DB layer
  (nonzero insert raises `IntegrityError`). No external writeback/delivery. Runtime state in SQLite
  outside the repo.
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes at
  schema 33 and now covers `daily_brief_notification_receipts`.
- Tests inject a temp app-support DB + a fixed `now` + a fake notifier; deterministic.

---

## 5. Known Limitations

1. `automation_execution` stays `deferred_not_blocking` — the final executor + morning-orchestrator
   wiring is unbuilt (the notify surface is ready to be wired as an optional step).
2. Real `osascript` emission only fires on a Mac with `daily_brief_notification.emit=true`; never in
   the suite.
3. Apply persists a V33 receipt only on actual emission (the notify ledger); the V28 audit receipt is
   emit-gated. Idempotency keys on a prior `emitted` receipt for the brief run/date.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V33 / 150 tables**; full matrix green (ruff, mypy 253, validate 4/4, pytest 2747 passed /
  0 fail, no-writeback proof at schema 33, phase-08a-gates 8/1/0/3, phase-08b-gates 14/0/0/1).
- A dry-run-default, idempotent, **local macOS notification surface** (V33
  `daily_brief_notification_receipts`, channel-pinned to `local_macos`, real-but-policy-gated
  `osascript` emission fail-closed behind `daily_brief_notification.emit`, emit-gated V28 receipt) with
  a passing `daily_brief_notification` gate — ready to be wired as an optional notify step in the
  morning orchestrator.
- The remaining build target is the **full automation executor** consuming the 08B observability +
  substrate + delivery + render + notify surfaces — flipping the last `deferred_not_blocking` gate.
