# ADR 261 — Forecast Phase 5: context-generator parameterization + full-package DB parity

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 5
- **Builds on:** ADR 258 (Phase 2 lineage), ADR 259 (Phase 3 v59 source-domain read parity), ADR 260 (Phase 4 DB read adapter); v58 (PR #29), lifecycle contract (PR #30), Phase 2 (PR #31), Phase 3 (PR #32), Phase 4 (PR #33, merge `cb333598`).

## Context

Phase 4 wired the v59 source-domain DB reads into the CFR forecast context generator behind a default-off toggle and proved parity **at the adapter boundary** (`load_*(file) == load_*(DB)`). It could not prove the full generated context **package** matches, because the generator was an unparameterized monolith: it read the live Synology root and built most state **at import time** (`SOURCE_PATHS`/`HASHES_BEFORE`, `budget_records`, the master-index loop, `build_procore_family_index()`), and `main()` wrote outputs under a hardcoded `OUT`. Running it twice (file-backed vs DB-backed) against temp roots was impossible.

Phase 5 **safely parameterizes** the generator so it runs against temp source/output roots, then proves file-backed and DB-backed context **packages** are equivalent when fed the same source-domain rows. Default production behavior is unchanged.

## Decision

### Refactor boundary — module-globals injection (mechanical, not a rewrite)

Every generator function reads config (`ROOT`/`OUT`/`STAMP`/`SRC_FILES`/`PROJECT_KEY`) and shared state (`master`, `decisions`, accumulators) via **module globals**. Rather than thread parameters through ~22 functions or rewrite as a class (deferred to a future cleanup phase), Phase 5 keeps that model and makes it injectable:

- `@dataclass(frozen=True) ContextPackageConfig(data_root, out_dir, stamp)`.
- `default_config()` reproduces today's defaults, with env overrides for controlled runs: `CFR_CONTEXT_DATA_ROOT`, `CFR_CONTEXT_OUT_DIR`, `CFR_CONTEXT_STAMP` (all unset ⇒ historical behavior).
- `_apply_config(config)` binds `ROOT`/`TWN_DIR`/`OWNER_DIR`/`PROCORE_DIR`/`STAMP`/`OUT`/`SRC_FILES`/`IGNORED` globals (no I/O).
- `_reset_state()` re-initializes **every** accumulator so a build is re-runnable in one interpreter (the parity test runs file-backed then DB-backed — and in the reverse order — in the same process).
- `_load_inputs_and_index()` holds the former import-time I/O block (source hashing, `budget_records` load, master loop, procore family index).
- `build_context_package(config) -> Path` = `_apply_config` → `_reset_state` → `_load_inputs_and_index` → the **unchanged** original `main()` body → `return OUT`.
- `main()` is now a thin wrapper: `build_context_package(default_config())`.

**emit_*/helper functions, calculations, filters, validations, sort orders, row shapes, and output schemas are unchanged.** The four import-time I/O statements were the only module-level code removed; the module-level path constants moved into `_apply_config`; the module-level accumulator initializers are retained (harmless at import) and mirrored in `_reset_state`.

### Default-behavior preservation + import safety

- Importing the module now performs **zero** I/O (verified: 0 files opened at import; `ROOT`/`SRC_FILES` are not defined at import). It reads no live source files, hashes nothing, builds no master records, creates no directories, writes no packages.
- With no env overrides, `default_config()` yields exactly today's `ROOT`/`STAMP`/`OUT`, so `main()` and the CFR `run-context` CLI behave identically. CFR's full 565-test suite remains green; no CLI change was required.

### Controlled temp-root generation + DB-backed mode

The Phase 5 parity test runs entirely under `tmp_path`:
1. Build a synthetic, self-contained source fixture (all required TWN/owner/procore files, one budget code threaded through every dependency so the generator reaches completion).
2. Migrate a temp SQLite DB to v59 and apply Phase 3 source-domain projection for the synthetic TWN package.
3. `build_context_package` file-backed → temp output root A.
4. `build_context_package` DB-backed (`HB_FORECAST_DB_BACKED_READS=1`, `HB_FORECAST_DB_PATH=<temp db>`) → temp output root B — reusing the Phase 4 adapter for only the three v59 source-domain row sets; everything else stays file-backed.
5. Compare normalized outputs.

DB-backed mode is fail-closed (Phase 4 semantics): missing rows, missing `HB_FORECAST_DB_PATH`, or a live/default DB path each raise `ForecastDbReadError` before any output is written — no silent fallback.

### Comparison + volatile normalization

All ~34 package outputs are parsed and compared structurally. **Only** these run-location/wall-clock fields are normalized: `generated_stamp`, `generated_timestamp_local`, `package_name` (manifest), `input_root`, manifest `output_files[].sha256`/`size_bytes`, and embedded output-directory paths (the README "Output folder" line) — neutralized by replacing the output path/name with placeholders. The verbatim `generate_forecast_context_package.py` script copy is skipped (identical). **Not** normalized: budget-code keys, cost-entry/monthly/actual values, row counts, mapping decisions, validation statuses/conclusions, or any financial/domain content. With identical source rows, file-backed and DB-backed packages are byte-equivalent after this normalization.

## Live safety

No Phase 5 test writes under the live Synology root or touches the live DB. Output paths are asserted under `tmp_path`. An optional read-only live-source smoke (copy live packages into temp, then run the harness) is `skipif`-gated on the Synology path and never runs in CI.

## Scope / deferrals (unchanged in Phase 5)

- Final CSV generation remains file-backed (no DB-backed final CSVs).
- Latest-glob / config-pin / run-state resolution unchanged.
- Full forecast-domain migration deferred; owner pay-app / Procore / control / staffing / schedule reads remain file-backed (not yet migrated).
- The −$3.42M reconciliation gap remains deferred.
- Live/default DB migration/application remains deferred.
- A class-based generator refactor is deferred to a later, explicitly-scoped cleanup phase now that full-package parity coverage exists.

## Consequences

- **No schema change** (`LATEST_SCHEMA_VERSION` stays 59; no v60). **No lifecycle-contract change** (`table_count` stays 387). No hb_assistant source changed.
- The generator is now import-safe, re-runnable, and temp-root-driven; full file-backed↔DB-backed package parity is proven in CI with a synthetic fixture.
- Live DB untouched (still v58, no v59 domain tables present); no live-root package output.
