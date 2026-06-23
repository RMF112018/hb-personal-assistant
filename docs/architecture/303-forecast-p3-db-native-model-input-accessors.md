# 303 — Forecast P3: DB-native model input accessors

- **Status:** Accepted
- **Date:** 2026-06-23
- **Phase:** Forecast-model remediation P3 (gap #3, "high")
- **Supersedes / relates:** ADR 301 (P2 consumption), ADR 302 (P2b value-overrides); builds on the
  v59 source-domain tables + read repos and the CFR `db_source_adapter` / `context_generation_runner`
  / `controlled_db_context_analysis` `db`-mode machinery from the JSON→SQLite transition phases.

## Context

A forecast *run* was package-source-first: `forecast_run_service.start_run` hardcoded the CFR
controlled workflow to `mode="file"`, requiring a hand-assembled source JSONL package on disk for
the three covered source domains (`budget_details`, `cost_entries`, `monthly_actuals`). The
DB-backed read path already existed and was proven (v59 read repos returning exact `raw_json` rows;
the CFR adapter/runner/workflow `db` mode with fail-closed guards; file-vs-DB package parity in
`test_forecast_context_runner_phase6.py`) — but nothing routed the product's run entry through it,
and there was no runtime opt-in.

## Decision

Add a default-off runtime flag `HB_FORECAST_DB_BACKED_INPUTS_ENABLED` and route `start_run` through
the existing CFR `mode="db"` path when it is on, sourcing the three covered domains from a
**non-live** v59 DB read-only. The file package remains the default and the fallback.

- **Flag** (`forecast_runtime_config.py`) follows the established trio+save pattern (ENV const,
  `DEFAULT_CONFIG` key, `resolve_db_backed_inputs_enabled` with precedence explicit > env >
  settings-file > `False`, surfaced in `build_runtime_status`, handled in `save_runtime_config`).
- **Routing** (`forecast_run_service.start_run`): resolve the flag locally (lazy import — the config
  module imports `ENV_DATA_ROOT`/`ENV_RUNS_ROOT` from the run service, so a module-level reverse
  import is circular); when on, resolve `db_path` and pass `mode="db", db_path=...` to the workflow.
  The decision is made inside `start_run`, not via a constructor arg, so the API factory and
  `forecast_db_config_run_service` stay uncoupled.
- **Fail closed before the workflow**: if the flag is on but `db_path` is unconfigured or resolves
  to the live/default DB (`is_live_db_path`), refuse — recorded as a failed run, the workflow is
  never called. `resolve_db_path()` defaults to the live DB, so a run never silently reads it.
  This is defense-in-depth ahead of the workflow's own (`mode='db'` requires `db_path`) and the
  adapter's (`mode=ro`, live-DB refusal) guards.
- **`no_live_writes`** is now derived from `work_root_outside_live_root` (true in both modes; a
  successful db-mode report guarantees a non-live, read-only DB).

## Non-goals

- No reading the live managed DB at runtime (CFR refuses it by design; a db-backed run targets a
  non-live v59 DB). Runtime sourcing from the managed DB is deferred to a later stage.
- No DB-wiring into `output_projection_engine` (reads analysis packages, not source inputs) or
  `decision_support_engine` (already reads v59 read-only). No new hb_assistant source adapter.
- No schema change, no v60+ migration, no lifecycle/table-count change, no CFR-subrepo source change.
- Packages remain the default and fallback; flag-off behavior is byte-identical to before.

## Consequences

- A run can source the covered model inputs from a non-live v59 DB behind an explicit opt-in,
  reducing the package-as-source dependency without removing packages (gap #3 intent).
- Validation: 7 routing/flag/fail-closed tests + the Phase 6 file-vs-DB parity machinery, all green.
- A full heavy end-to-end db-mode run is gated by the pre-existing Group D environmental condition
  (CFR not importable in the venv → analysis subprocess relative-import failure), owned by P10; it
  is not introduced by P3. See the P3 evidence bundle for the honest scope note.
