# 187 — Cross-Platform Launcher & Scheduled Source-Refresh

**Objective:** add the operational layer on top of the unified source-refresh
orchestrator — two distinct launchers (Dev / Production) with a Quit/Run-in-Background
close policy, and a repo-owned, cross-platform scheduler that runs the unified refresh
daily at 8 PM local with app-level catch-up. The scheduled job calls the unified
orchestrator, never a manual Graph/Procore command chain.

(The objective named this record 186; 186 is already
`186-procore-multi-project-sync-aggregation.md`, so this is 187.)

## Launcher (`src/hb_assistant/launcher/`)

Pure-Python process model — **no hard GUI dependency**.

- **`profiles.py`** — `resolve_profile("dev"|"production")` returns a `Profile`
  resolving DB/log/evidence/cache/scheduler-state/launcher-session paths, modes, and
  live-read policy. **Strict isolation:** production uses the configured app-support
  root; dev derives a separate `"<root> (Dev)"` root via a copied `AppConfig` +
  `PathPolicy`. A `ProfileCollisionError` is raised if dev and production ever resolve
  to the same root/DB. `snapshot_source_db()` copies a source SQLite into the Dev DB
  via the read-only backup API (never mutating the source), requires `--confirm` to
  overwrite, and emits a metadata-only receipt.
- **`process_manager.py`** — `ProcessManager` spawns/tracks/terminates child processes
  and persists a per-environment session JSON (PIDs survive across CLI invocations).
  Cross-platform: POSIX process groups + SIGTERM→SIGKILL; Windows
  `CREATE_NEW_PROCESS_GROUP` + `taskkill`.
- **`service.py`** — `LauncherService` builds the managed-process specs
  (backend `uvicorn --factory`, frontend `npm run dev` / static `dist`, MCP
  `second-brain mcp serve --stdio`, foreground scheduler). Specs are profile/config
  derived; the concrete commands are overridable fallback defaults. Optional surfaces
  degrade to `skipped`/`unavailable`. Dev children get `HB_PA_CONFIG` pointing at a
  dev config so they resolve the isolated dev root.
- **`close_policy.py`** — `quit` terminates all managed processes + writes a metadata
  shutdown receipt; `background` terminates UI/frontend, keeps `keep_in_background`
  services (MCP, scheduler) alive, marks the session background-active. `launcher stop`
  ends a background session later.
- **`webview_shell.py`** — optional, lazy-imported pywebview window whose `closing`
  event routes to the close policy. Never imported at package load; everything works
  without pywebview.

CLI `cli/launcher.py`: `dev`, `production`, `status`, `stop`, `close`, `snapshot-dev-db`.

## Scheduler (`src/hb_assistant/scheduler/`)

- **`state.py`** — JSON `SchedulerState` (environment, job_id, schedule_time_local,
  timezone, catch_up_on_wake, last_started/finished_at, last_successful/attempted
  schedule_date, last_status, last_receipt_path, consecutive_failures,
  next_expected_run, current_process_ids).
- **`due.py`** — pure (caller injects `now`): `compute_next_run`, `is_missed`,
  `decide_catch_up`. Runs daily at the local time; catches up once on the next
  wake/start for a missed occurrence; never double-runs a schedule date
  (`last_successful_schedule_date` guard).
- **`daily_source_refresh.py`** — `DailySourceRefreshJob` calls
  `SourceRefreshOrchestrator` in-process with **explicit** live-read options (never
  defaults). Dev → `mock_data=True` (no creds, no live auth/status/probe). Production →
  local-only unless config enables live reads; `HB_PROCORE_LIVE` is set only for the
  duration of a live run. Emits a metadata-only receipt distinguishing
  `local_only` vs `live_source`. Records the `assistant_runs` ledger.
- **`runner.py`** — `SchedulerRunner.run_once` / `tick(now)` drive the due decision.
- **`backends/`** — launchd plist, Windows Task Scheduler XML, systemd user
  service+timer (`OnCalendar`, `Persistent=true`), and a foreground loop fallback.
  Dry-run/preview writes no OS files. **Native backends only fire the repo runner**
  (`scheduler run … --if-due`); app-level state owns catch-up, so wake/Persistent
  replays cannot double-run.

CLI `cli/scheduler.py`: `install`, `uninstall`, `status`, `run`, `due`.

## Source-refresh changes

`RefreshOptions` gains `mock_data`, `allow_procore_live`, `allow_graph_live` (defaults
True preserve the manual `refresh-sources --apply --confirm` behavior). The procore
and graph stages short-circuit to local-only when `mock_data` or the per-source live
flag is off — and, critically, never call Procore/Graph auth/status/probe in that case.
The `refresh-sources` CLI gains `--mock-data`. `config.automation.scheduler`
(`SchedulerConfig`) gates production live reads (all OFF by default).

## Guardrails

No Procore/M365 writeback; no raw bodies/URLs/tokens; no vectors in SQLite; scheduler
and shutdown receipts are metadata-only; dev mock never reads live external; production
live refresh uses the existing confirm/live gates; closing the window never orphans
unmanaged processes (background mode is explicit and inspectable). Dev and Production
DB/state are strictly isolated (tests fail on path collision).

## Evidence / tests

`docs/evidence/source-refresh/` gains the scheduler-install, scheduler-catch-up,
dev-launcher, production-launcher, launcher-close-background, and
scheduled-source-refresh-closeout proof pairs (generated by
`scripts/proofs/launcher_scheduler_evidence_proof.py`).
`tests/test_launcher_scheduler.py` covers isolation/collision, plan-mode no-spawn,
close quit/background, background-stop, due/catch-up/no-double-run, dry-run writes
nothing, backend artifact validity, explicit live options, env-armed-only-for-run, and
snapshot source-immutability. New modules are in strict ruff + mypy scope.
