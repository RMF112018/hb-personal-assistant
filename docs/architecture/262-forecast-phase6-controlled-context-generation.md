# ADR 262 — Forecast Phase 6: controlled, default-off DB-backed context generation

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 6
- **Builds on:** ADR 258 (Phase 2 lineage), ADR 259 (Phase 3 v59 source-domain read parity), ADR 260 (Phase 4 DB read adapter), ADR 261 (Phase 5 context-generator parameterization + full-package parity); v58 (PR #29), lifecycle contract (PR #30), Phase 2 (PR #31), Phase 3 (PR #32), Phase 4 (PR #33), Phase 5 (PR #34, merge `9f62754f`).

## Context

Phases 3–5 made DB-backed context generation **possible** and **proven**: Phase 3 landed the v59 source-domain tables with read parity, Phase 4 added a default-off CFR-local read adapter, and Phase 5 parameterized the generator (`build_context_package(config)`) and proved full file-backed↔DB-backed package parity in temp roots.

What was still missing was an **operator-/test-facing way to intentionally drive** a DB-backed package build from explicit inputs. Today, DB-backed mode is reachable only by hand-setting two env vars (`HB_FORECAST_DB_BACKED_READS=1`, `HB_FORECAST_DB_PATH`) and relying on `default_config()`'s `CFR_CONTEXT_*` env overrides. There is no controlled entry point that validates inputs, isolates environment side effects, and fails closed on unsafe inputs.

Phase 6 adds that controlled workflow layer — a small runner module plus an optional CLI command. It is **not** the final forecast CSV cutover, and it changes **no** production defaults.

## Decision

### A narrow runner, not another generator refactor

Phase 6 adds `construction_financial_review/context/context_generation_runner.py`, a thin orchestrator over the Phase 5 generator. It does **not** reopen generator internals — no change to calculations, output schemas, validation, sorting, source row shapes, or package semantics. Its only job is to make an intentional controlled run safe and explicit:

`run_context_generation(*, data_root, out_dir, stamp, db_backed=False, db_path=None, project_key="tropical") -> dict`

- Constructs a `ContextPackageConfig(data_root, out_dir, stamp)` **directly** from explicit arguments — it does not depend on the ambient `CFR_CONTEXT_*` env overrides.
- Calls `build_context_package(config)` once and returns structured run metadata, including the generated `output_package` path.
- Keeps CFR's stdlib-only independence: `hb_assistant` is imported **lazily**, only inside the DB-backed branch (to refuse the live/default DB), mirroring the Phase 4 adapter.

### Default-off DB-backed semantics + explicit paths

- File-backed is the default (`db_backed=False`); DB-backed is opt-in per call.
- A controlled run requires **explicit** `data_root`, `out_dir`, and `stamp` (deterministic). DB-backed mode additionally requires an explicit `db_path`.

### Fail closed before build execution

All safety validation happens **before** the build runs and **before** any output directory is created:

- `data_root`, `out_dir`, `stamp` must be provided; `project_key` must be `tropical` (Phase 6 is Tropical-only — multi-project generalization is deferred, not hidden scope).
- `out_dir` must not already exist (mirrors the generator's `OUT.mkdir(exist_ok=False)`; rejected early for a clean error).
- `out_dir` must not be at or under the live Synology forecast data root (`generate_forecast_context_package._DEFAULT_DATA_ROOT`) — refused.
- DB-backed mode requires `db_path`, and refuses the live/default **or unresolvable** DB path via `is_live_db_path()` (which fails closed — returns `True` — when a path cannot be resolved, so one check covers both).
- DB-backed mode never falls back to file rows if the v59 rows are missing: the Phase 4 adapter raises `ForecastDbReadError` (`"no DB rows"`) and that propagates from the build. The failure occurs while loading `budget_details`, i.e. before any output directory is created.

### Explicit environment isolation

The runner manages the two Phase 4 toggles around exactly one build, with `try/finally` restoration of the prior values (including restoring "unset"):

- `db_backed=True`: set `HB_FORECAST_DB_BACKED_READS=1` and `HB_FORECAST_DB_PATH=<explicit db>` for the duration.
- `db_backed=False`: temporarily **clear** both toggles so ambient shell state cannot silently promote a file-backed controlled run to DB-backed.

Restoration runs on both the success and failure paths.

### CLI command (operator-safe, non-breaking)

A new `context-generate` subcommand is added to the CFR argparse CLI:

```
python -m construction_financial_review.cli context-generate \
  --project tropical --data-root <path> --out-dir <path> --stamp <stamp> \
  [--db-backed --db-path <temp.sqlite>]
```

It requires explicit paths, prints structured JSON metadata on **stdout** (the generator's own progress chatter is redirected to stderr to keep stdout a clean machine-readable channel), and returns nonzero (3) on any refusal — unsafe/missing DB path, live/default DB, live-root output, or missing DB rows. The existing `run-context` command and every other generator command are untouched and remain file-backed by default.

## Tests & parity strategy

`tests/test_forecast_context_runner_phase6.py` reuses the Phase 5 synthetic, self-contained fixture (duplicated, not imported, so the proven Phase 5 parity test stays independent) and proves:

- controlled file-backed and DB-backed runs that write only under `tmp_path`;
- file-backed vs DB-backed package parity **through the runner** using the Phase 5 normalization helper;
- environment isolation — prior toggles restored after success and after failure; a file-backed run is unaffected by ambient `HB_FORECAST_DB_BACKED_READS=1`;
- fail-closed paths — no `db_path`, live/default DB, missing v59 rows, live-root `out_dir`, existing `out_dir`, unsupported project;
- preservation of existing defaults — `default_config()` unchanged with no env, generator `main()` still the thin wrapper, `run-context` still routes;
- CLI behavior — file-backed and DB-backed success under `tmp_path`, and nonzero refusals for missing `--db-path`, live DB, and live-root output.

No Phase 6 test touches the live DB or writes under the live data root.

## Scope / deferrals (unchanged in Phase 6)

- Final forecast CSV DB-backed generation (no DB-backed final CSVs — Phase 6 is context packages only).
- Latest-glob / config-pin / run-state resolution unchanged.
- Full forecast-domain migration deferred; owner pay-app / Procore / control / staffing / schedule reads remain file-backed.
- Production DB-backed default enablement deferred — DB-backed mode stays opt-in.
- The −$3.42M reconciliation gap remains deferred.
- Live/default DB migration/application remains deferred.
- A class-based generator cleanup remains deferred.

## Consequences

- **No schema change** (`LATEST_SCHEMA_VERSION` stays 59; no v60). **No lifecycle-contract change** (`table_count` stays 387). **No `hb_assistant` source changed** (the runner reuses Phase 3/4 reads and `is_live_db_path` via lazy import).
- There is now a safe, explicit, default-off way to run context generation from DB-backed v59 source-domain rows in a controlled temp-root workflow, without changing existing production defaults or touching final CSV generation.
- Changed surface is additive: one new CFR runner module, one new CFR CLI subcommand (+ a `contextlib` import and stdout-isolation), one new test module, and this ADR.
- Live DB untouched (still v58, no v59 domain tables present); no live-root package output.
