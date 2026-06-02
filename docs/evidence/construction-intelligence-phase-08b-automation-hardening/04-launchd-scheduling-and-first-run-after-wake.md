# Phase 08B — Prompt 04: LaunchAgent Scheduling & First-Run-After-Wake

**Status:** Implemented (additive). Schema **V28 reused** (no migration); package stays `1.3.0`.
**Baseline:** atop `ffc135f` (08B Prompt 03; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** Hardened install / preview / apply / uninstall surface + first-run-after-wake catch-up
evaluation for the second-brain daily-brief LaunchAgent, with Phase 08B structured reason codes.
The `launchd_install` data-quality gate flips from `deferred_not_blocking` to `pass`;
`automation_execution` stays deferred.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/launchd_scheduler.py` (new) — models +
  `evaluate_launchd_schedule`, `evaluate_first_run_after_wake`, `preview_launchd_install`,
  `apply_launchd_install` / `uninstall_launchd` (real-but-policy-gated, fail-closed),
  `run_launchd_schedule_agent` (emit-gated V28 receipt), `build_launchd_scheduler_proof`.
- `src/hb_assistant/construction/second_brain/data_quality.py` — import + `launchd_install` flipped
  to `_proof_gate(build_launchd_scheduler_proof())`.
- `src/hb_assistant/cli/second_brain.py` — `automation` group: `launchd-status`, `catch-up-status`,
  `launchd-install`, `launchd-uninstall`.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `launchd` reason-code keys +
  `first_run_after_wake` section + 5 appended reason codes.
- `src/hb_assistant/resources/json/phase_08b_automation_policy_contract.json`,
  `phase_08b_data_quality_gates.json` — appended reason codes.

Tests (new): `tests/test_launchd_scheduler_agent.py`, `tests/test_second_brain_launchd_cli.py`.
Tests (updated): `tests/test_phase_08b_data_quality_gates.py` (launchd_install now pass),
`tests/test_phase_08b_contracts_and_seed.py` (+ scheduling reason-code membership test).

Docs: `docs/architecture/76-phase-08b-launchd-scheduling-and-first-run-after-wake.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `ruff format` (touched files) | clean |
| `mypy src` | Success — no issues in **246** source files |
| `pytest tests/test_launchd_scheduler_agent.py tests/test_second_brain_launchd_cli.py tests/test_phase_08b_data_quality_gates.py tests/test_phase_08b_contracts_and_seed.py` | all passed |
| `pytest -m "not integration and not live and not manual"` | **2603 passed, 4 skipped, 1 deselected** (2607 collected; 0 failures, 0 errors; +22 new tests) |
| `construction-agent validate --json` | 4/4 passed (schema_version=28) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 28 |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **7 pass / 0 warning / 0 fail / 1 deferred**, `launchd_install=pass` |
| `second-brain automation launchd-status --json` | overall=attention, schedule=LAUNCHD_NOT_INSTALLED, catch_up=CATCH_UP_NEEDED (read-only; nothing installed) |
| `second-brain automation catch-up-status --json` | CATCH_UP_NEEDED |
| `second-brain automation launchd-install --apply --confirm --json` | status=blocked, reason=LAUNCHD_INSTALL_DISABLED_BY_POLICY, plist_written=false, launchctl_invoked=false, external_writeback_performed=0 |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V28 reused** (no migration); `table_count` stays **144**; no new
  table; `_PHASE_08A_TABLES` unchanged (the receipt table is already in the no-writeback scan scope).
- **Dry-run default:** `launchd-install` / `launchd-uninstall` preview by default; mutation needs
  `--apply --confirm` **and** is fail-closed by policy.
- **No writeback / delivery / raw content:** the emit-gated receipt is metadata-only (status +
  reason code) with the nine guard `CHECK(col = 0)` columns; proof + receipt blobs scanned for
  forbidden tokens; apply/uninstall never invoke an external system.
- **Actionable reason codes:** `LAUNCHD_NOT_INSTALLED`, `SCHEDULE_DRIFT`, `LAUNCHD_INSTALLED_OK`,
  `LAUNCHD_INSTALL_DISABLED_BY_POLICY`, `CATCH_UP_NEEDED`, `CATCH_UP_NOT_NEEDED`, `CATCH_UP_STALE`.
- **Coverage of success / failure / blocked / stale / dry-run:** installed-ok / drift /
  not-installed; catch-up needed / not-needed / stale; apply blocked-by-policy (exact shape) and the
  real-write success path (temp dir + override policy + mocked `launchctl`); preview dry-run.

---

## 4. Guardrails Verified

- Real `~/Library/LaunchAgents` and real `launchctl` are never touched in tests or validation — the
  success path runs only against an injected temp dir with a mocked runner.
- Apply/uninstall remain fail-closed while the seed carries `dry_run_install_only: true`.
- No external writeback, no external delivery (email/Slack/Teams/SMS/push/webhook/Graph sendMail).
- No raw email bodies / document text / calendar payloads / prompts / responses / signed or download
  URLs persisted; receipts are metadata-only.
- Generated plists/logs use safe paths outside the repo (Application Support / `~/Library`).
- Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3); no-writeback proof passes.

---

## 5. Known Limitations

1. `automation_execution` (retry/backoff orchestration, weekend gating, run-ledger bridge) stays
   `deferred_not_blocking` — owned by the next 08B prompt.
2. Real launchd install is implemented but **future-enableable**: it stays blocked until an operator
   flips `launchd.dry_run_install_only` to `false` in the seed.
3. First-run-after-wake detection is heuristic (ledger + schedule-time comparison), not an OS
   sleep/wake hook.
4. The legacy morning-run LaunchAgent (`automation/launchd_manager.py`) is a separate agent and is
   intentionally untouched.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V28 / 144 tables**; full matrix green (ruff, mypy 246, validate 4/4, pytest 2603
  passed / 4 skipped / 0 fail, no-writeback proof, phase-08a-gates 8/1/0/3, phase-08b-gates 7/0/0/1).
- A read-only LaunchAgent scheduling + catch-up surface with structured reason codes, an emit-gated
  V28 receipt (`agent_id='launchd_scheduler_agent'`), and a real-but-policy-gated install/uninstall
  mechanism that is future-enableable via the seed flag.
- The remaining build target is the **automation execution layer** (retry/backoff, weekend gating,
  run-ledger bridge) — flipping the last `deferred_not_blocking` gate.
