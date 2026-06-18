# ADR 260 — Forecast Phase 4: generator DB-backed source read adapter

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 4
- **Builds on:** ADR 258 (Phase 2 lineage projection), ADR 259 (Phase 3 v59 source-domain read parity); v58 foundation (PR #29), lifecycle contract (PR #30), Phase 2 (PR #31), Phase 3 (PR #32, merge `5efcfe5e`).

## Context

Phase 3 added the three v59 source-domain tables (`forecast_budget_details`,
`forecast_cost_entries`, `forecast_monthly_actuals_by_budget_code`) and DB read
repositories that round-trip JSONL↔SQLite, but nothing consumed them. Phase 4 wires those
DB-backed reads into the first real generator consumer — the CFR forecast **context
generator** — behind an explicit, default-off toggle, and proves the generator receives
identical source rows in both modes.

This is not a full DB migration, not final-CSV migration, not latest-glob replacement.
With the toggle off (the normal case) nothing changes and behavior is byte-for-byte
equivalent.

## Decision

### Why only the v59 source-domain slice, and which read boundary

The context generator reads exactly the three TWN cost-forecast JSONL sources at three
sites in `generate_forecast_context_package.py`:

| Site | Source | Generator behavior |
|---|---|---|
| line 234 (module level) | `budget_details.jsonl` | no sort (source order) |
| `emit_cost_entries()` (line ~410) | `cost_entries.jsonl` | sorts by `source_row` after load |
| `emit_monthly_actuals()` (line ~481) | `monthly_actuals_by_budget_code.jsonl` | sorts by `(budget_code_key, month)` after load |

Each site does `list(read_jsonl(SRC_FILES[...]))`. Phase 4 replaces only these three reads
with a single adapter call. Other reads (owner/procore) are untouched.

### Import-boundary decision — CFR-local adapter, lazy hb_assistant import

The boundary is technically clean (CFR→hb_assistant is one-way, no circular imports,
verified live), **but** CFR is deliberately stdlib-only (numpy/scipy), declares no
hb_assistant dependency, runs the generator as a standalone subprocess, and Phases 2–3 kept
the two packages decoupled (hb_assistant reads CFR *files* as plain JSON; it never imports
CFR). To preserve that independence, Phase 4 adds a **CFR-local adapter**
(`construction_financial_review/context/db_source_adapter.py`):

- **Toggle off (default):** the adapter calls the generator's existing `read_jsonl` and
  returns its rows verbatim. It does **not** import hb_assistant, resolve a DB path, open
  SQLite, or inspect any env beyond the single toggle. No top-level hb_assistant import
  exists anywhere in CFR — the only import is inside the DB-active branch. (A subprocess
  test asserts `hb_assistant` is absent from `sys.modules` after a toggle-off load.)
- **Toggle on:** the adapter **lazily** imports hb_assistant's Phase 3 read repositories and
  reads the v59 rows. Schema ownership and read logic stay in hb_assistant; CFR duplicates
  no projection/write/schema code. Phase 4 added three thin file-order readers to
  `hb_assistant.construction.forecast.source_domain_repository`
  (`read_*_in_file_order`, ordered by `source_row_number`) so the DB path is a faithful
  drop-in for `list(read_jsonl(...))`.

The generator imports the adapter dual-mode (`from db_source_adapter import …` in script
mode via `sys.path[0]`, with the package path as fallback), matching how the generator
already runs as a standalone script.

### Toggle semantics

- `HB_FORECAST_DB_BACKED_READS=1` activates DB-backed reads; unset/any other value → file-backed (default).
- `HB_FORECAST_DB_PATH=/path/to/temp.sqlite` supplies the explicit DB path.
- The CFR CLI already runs the generator with `env=dict(os.environ)`, so both vars flow to
  the subprocess naturally — **no CLI change was needed**, and the toggle has a real
  generator consumer.

### source_package identity

DB-backed reads query by `(project_key, source_package)`. **Verified against Phase 3
projection** (`source_reader.package_name_of` → `source_package.name`): the stored
`source_package` is the package **directory basename**. The adapter therefore passes
`TWN_DIR.name` (= `"twn_cost_forecast_json_package"`) and `PROJECT_KEY` (= `"tropical"`),
matching exactly what Phase 3 wrote.

### Fail-closed behavior (toggle on; never silently fall back to files)

- `HB_FORECAST_DB_PATH` unset/empty → raise `ForecastDbReadError`.
- Resolved path equals the live/default DB (`PathPolicy().get_db_path()`) **or** path
  resolution fails → raise (reuses `engine.is_live_db_path`, which fails closed on
  resolution error).
- hb_assistant import fails → raise.
- The selected source has zero rows for the `(project_key, source_package)` pair → raise.

### Ordering

The adapter is a source-row **provider only** — it returns rows in source-file order
(`source_row_number`) and never sorts. The generator keeps its own `.sort()` calls
immediately after loading (for cost_entries / monthly_actuals), exactly as today, so
downstream behavior is identical given identical input rows.

## Generator-level parity strategy

Parity is proven at the **adapter boundary**: for all three sources,
`load_*(file-backed) == load_*(DB-backed)` returns identical row lists in identical order —
the exact in-memory source rows the generator's emit functions consume before
serialization. Because the generator is deterministic given those rows (stdlib, sorted,
Decimal math), identical adapter outputs prove the DB-backed path can supply the same source
data without changing generator behavior.

**Full context-package run comparison is explicitly deferred.** The current context
generator is not safely injectable: it hardcodes the live data root (`ROOT`/`OUT`),
reads `budget_details` at import time (module-level line 234), and writes package outputs
under the live root (`OUT.mkdir(exist_ok=False)`). Running it file-backed-vs-DB-backed for a
package diff would write under the live root and require live data — both forbidden by the
Phase 4 boundaries. Phase 4 therefore proves parity at the last safe boundary before
serialization and defers full temp-root package diffing to a later phase that intentionally
parameterizes the generator. ROOT/OUT/SRC_FILES/import-time reads/`main()` were **not**
refactored in this phase.

## Scope / deferrals (unchanged in Phase 4)

- Final CSV generation remains file-backed.
- Latest-glob / config-pin / run-state resolution remains unchanged.
- Full forecast-domain model migration remains deferred.
- The −$3.42M reconciliation gap remains deferred.
- Live/default DB migration and application remain deferred.

## Consequences

- **No schema change** (no v59 DDL touched, no v60); `LATEST_SCHEMA_VERSION` stays 59.
- **No lifecycle-contract change**; `table_count` stays 387.
- hb_assistant gains three additive file-order read helpers (read layer it already owns).
- CFR gains one stdlib-only adapter module and three one-line read-site substitutions;
  default behavior is byte-identical (CFR's own 565-test suite stays green).
- The toggle is implemented because it now has a real generator consumer; default-off, and
  unused unless explicitly activated with an explicit temp DB path.
