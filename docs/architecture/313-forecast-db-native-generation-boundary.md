# 313 — Forecast Run Center: DB-native generation boundary (fail-closed)

- Status: accepted
- Date: 2026-06-25
- Phase: Forecast Run Center remediation P3 (DB-native boundary)
- Related: ADR 310 (P9 UI/API readiness), ADR 311 (P9b durable live write/backup); PRs #134 (honest
  failure reporting), #135 (first-run / sparse-data readiness maturity)

## Context

The Forecast Run Center now supports explicit project selection (#131), a DB-backed primary Generate
action (#132), Results Summary + Forecast Health (#133), honest generation-failure reporting (#134),
and a first-run / sparse-data readiness **maturity** model (#135). The remaining gap is **runtime
generation capability**: the DB-output-write Generate-Forecast route presents as DB-native but is not.

This ADR records the decision to make that boundary explicit and fail closed, rather than implement
DB-native generation (which requires a dedicated CFR/subrepo remediation) or silently fall back to the
file-backed workflow.

## Current repo-truth

The DB-output-write path (`POST /api/forecast/runs/db-config` with
`HB_FORECAST_RUN_OUTPUT_DB_WRITE_ENABLED=1`) is the only caller of
`forecast_run_output_persistence_service.generate_and_persist()` →
`_run_generation()`, which:

- resolves the configured `data_root` and globs for a `*cost_forecast_json_package` directory;
- runs the CFR workflow `run_controlled_context_analysis_workflow(mode="file")`; and
- persists via `live_db_run_output_projection`, which **requires file-backed `source_package` and
  `analysis_package` directories**.

So the path is **DB-native-intended but file-backed end-to-end**. CFR's DB-backed context generator is
not production-ready for this app path and reportedly fails closed on zero monthly-actuals rows, so a
true DB-native first-run forecast (across the P2 maturity states: baseline-only, cost-informed,
schedule-informed, full-context) requires future CFR work. Prior to this phase, a missing source
package surfaced as `source_package_missing` (#134) — technically accurate but understating the gap: a
genuinely DB-native path would not need that file at all.

Readiness/maturity (P2) and runtime generation capability are **separate axes**. A project may be
readiness-classified `baseline_only` / `cost_informed` / `schedule_informed` and still be unable to
execute through the current engine. That is acceptable as long as the runtime failure is honest.

## Decision

The DB-output-write Generate-Forecast route is **DB-native-intended and fails closed up front** with
the coded failure `db_native_generation_not_implemented`:

- `generate_and_persist(..., db_native_intended=True)` (the API route) returns a failed receipt
  **before any file lookup, `_run_generation()` call, or CFR workflow** — `db_persisted=false`,
  `package_generated=false`, a curated path-free failure message, and **no** forecast-output rows,
  package manifests, or evidence rows. It never falls back to file-backed generation, regardless of
  whether a `*cost_forecast_json_package` happens to exist.
- File-backed generation still exists **internally/legacy** behind the explicit
  `db_native_intended=False` mode (exercised by unit tests / any legacy caller). That mode retains the
  prior behavior: `source_package_missing` when the package is absent, `generation_calculation_failed`
  on other generation errors, else real persistence. **It is not the DB-native Generate-Forecast path.**
- No CFR subrepo edits. No DB-native generation spike.

The UI maps `db_native_generation_not_implemented` to safe, path-free copy that states the project's
readiness result is still valid, the engine is not DB-native yet, and no live data or export package was
produced. Readiness continues to be driven by the P2 maturity fields, not by this runtime failure code.

## Consequences

- The API/UI are honest: the DB-native route no longer implies a capability it lacks, and no run
  silently executes through the file-backed workflow.
- P2 readiness semantics are preserved: sparse / first-run projects are still classified by maturity and
  remain selectable/generatable; the runtime capability gap does not degrade readiness.
- No live data is mutated and no user-facing package is produced on this path.

## Future required CFR work (for true DB-native first-run forecasting)

- A DB-source context generator that supports sparse / zero-monthly-actuals projects.
- A DB-native analysis input adapter (no file `analysis_package` dependency).
- A DB-native output projection that does not require file `source_package` / `analysis_package` dirs.
- A first-run forecast path that works across the P2 maturity states (baseline-only → full-context).
- Certification/testing proving no package dependency remains for DB-native generation.

## Guardrails

- No live-DB mutation in tests (temp/copied DBs only); no external calls (Procore/Graph/Sage); no
  user-facing export/download packages from Generate Forecast; no raw path / payload / secret leakage in
  API or UI responses.
