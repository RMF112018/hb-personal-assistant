# 76 — Phase 08B: LaunchAgent Scheduling & First-Run-After-Wake (Prompt 04)

**Status:** Implemented (additive). Schema **V28 reused** (no migration); package stays `1.3.0`.
**Baseline:** atop `ffc135f` (08B Prompt 03; 08A closeout `954a518` is ancestor).
**Scope:** A hardened install / preview / apply / uninstall surface plus first-run-after-wake
catch-up evaluation for the second-brain daily-brief LaunchAgent, with the Phase 08B structured
reason-code vocabulary. Flips the `launchd_install` data-quality gate from
`deferred_not_blocking` to `pass`.

## Context

Two pre-existing launchd surfaces frame this work:

- The **legacy morning-run LaunchAgent** (`automation/launchd_manager.py`, `cli/automation.py`,
  label `com.hb.personal-assistant.morning`) schedules the old `hb-assistant run morning`
  orchestrator. It is a *different* agent and is **not** touched by this prompt.
- The **daily-brief schedule preview** (`daily_brief/scheduling.py::build_daily_brief_schedule_preview`,
  label `com.hb.personal-assistant.second-brain-daily-brief`) is preview-only and its docstring
  explicitly defers "real install/enable" to Phase 08B. This prompt is that work.

The Phase 08B automation policy seed already declared `launchd.dry_run_install_only: true` and
the reason codes `LAUNCHD_NOT_INSTALLED` / `SCHEDULE_DRIFT`.

## Design

New module `construction/second_brain/launchd_scheduler.py` (mirrors `automation_health.py`):

- **`evaluate_launchd_schedule(*, db_path, launch_agents_dir)`** — read-only. Resolves the desired
  plist/schedule from `build_daily_brief_schedule_preview` (single source of truth) and reads the
  real plist at `<launch_agents_dir>/{label}.plist` (default `~/Library/LaunchAgents`). Outcomes:
  `LAUNCHD_NOT_INSTALLED`, `SCHEDULE_DRIFT` (StartCalendarInterval ≠ policy time, or unreadable),
  `LAUNCHD_INSTALLED_OK`.
- **`evaluate_first_run_after_wake(*, db_path, now)`** — read-only (no migration). Reads the most
  recent `daily_brief_runs.generated_utc` and compares to the local date + policy schedule time +
  `first_run_after_wake.stale_after_days`: `CATCH_UP_STALE` (older than the threshold),
  `CATCH_UP_NEEDED` (no run today and past the scheduled fire — machine likely slept through it),
  `CATCH_UP_NOT_NEEDED`. Fail-open to `CATCH_UP_NEEDED` on a parse failure.
- **`preview_launchd_install` / `apply_launchd_install` / `uninstall_launchd`** — the apply/uninstall
  surface is **real-but-policy-gated, fail-closed**. The plist-write + `launchctl` code path exists,
  but while the seed carries `dry_run_install_only: true` (or `confirm` is absent) an
  `--apply --confirm` request returns `{status: "blocked", reason_code:
  "LAUNCHD_INSTALL_DISABLED_BY_POLICY", plist_written: false, launchctl_invoked: false,
  external_writeback_performed: 0}` and writes nothing. The real-write path is reachable only with an
  override policy (`dry_run_install_only=False`) **and** `confirm` **and** an injected `launchctl`
  runner — exercised only in tests against a temp LaunchAgents directory + temp log dir.
- **`run_launchd_schedule_agent(*, emit_receipt=False)`** — evaluates schedule + catch-up and returns
  a combined `LaunchdSchedulerStatus`. When `emit_receipt`, persists one metadata-only V28
  `second_brain_agent_run_receipts` row (`agent_id='launchd_scheduler_agent'`,
  `run_kind='launchd_schedule_eval'`, status + reason code only) via the existing
  `build_agent_run_receipt` / `write_agent_run_receipt` writers. Off by default.
- **`build_launchd_scheduler_proof()`** — deterministic proof on a temp migrated DB that drives the
  `launchd_install` gate.

### CLI (`second-brain automation` group)

`launchd-status` (read-only; `--emit-receipt` off by default), `catch-up-status` (advisory),
`launchd-install` (preview default; `--apply --confirm` fail-closed by policy), `launchd-uninstall`
(symmetric). All mirror the `automation health` shape: `--json` default, a `guardrails` block, and
forbidden-token-safe output.

### Policy / contract changes (additive)

- `resources/config/phase_08b_automation_policy.seed.yaml` — extended `launchd:` with
  `installed_ok_reason_code` / `disabled_by_policy_reason_code`; added a `first_run_after_wake:`
  section (`enabled`, `stale_after_days: 3`, catch-up reason codes); appended 5 reason codes.
- `resources/json/phase_08b_automation_policy_contract.json` and `phase_08b_data_quality_gates.json`
  — appended the same reason codes (keeps the seed⊆contract validation green). `required_fields`
  unchanged (the `launchd_install` gate name is reused).

### Gate flip

`data_quality.py::evaluate_phase_08b_data_quality_gates` replaces the deferred `launchd_install`
gate with `_proof_gate("launchd_install", build_launchd_scheduler_proof())`. `automation_execution`
(retry/backoff/weekend execution + run-ledger bridge) remains `deferred_not_blocking` — owned by a
later prompt. phase-08b-gates moves from 6 pass / 2 deferred to **7 pass / 1 deferred**.

## Guardrails

No schema change (V28 reused; `table_count` 144 unchanged; `_PHASE_08A_TABLES` unchanged — the
receipt table is already in the no-writeback scan scope). No external writeback, no external
delivery, no raw-content persistence. Apply/uninstall dry-run by default and fail-closed by policy;
real installs require flipping the seed flag and are never performed during tests or validation
(temp dir + mocked `launchctl` only). Generated plists/logs live outside the repo.

## Known limitations / next

- `automation_execution` (retry/backoff orchestration, weekend gating, run-ledger bridge) is still
  deferred — the next 08B prompt.
- Real launchd install is implemented but **future-enableable**: it stays blocked until an operator
  flips `launchd.dry_run_install_only` to `false` in the seed.
- Wake-event detection is heuristic (ledger + schedule-time comparison), not an OS sleep/wake hook.
