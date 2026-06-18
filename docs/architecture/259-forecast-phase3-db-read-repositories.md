# ADR 259 — Forecast Phase 3: v59 source-domain tables + DB-backed read repositories

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 3
- **Builds on:** ADR 258 (Phase 2 lineage projection); v58 foundation schema (PR #29); lifecycle-contract reconciliation (PR #30); Phase 2 projection (PR #31, merge `d9a1a9aa`).

## Context

Phase 2 projected forecast *lineage* (run/project/source/manifest/validation rows) into
the five v58 foundation tables. It proved schema ownership and idempotent projection, but
proved nothing about whether real forecast *source data* can live in SQLite and be read
back faithfully. Phase 3 is the first **DB-backed domain read-parity** slice: project a
narrow, concrete set of Tropical source rows into SQLite and read them back in the same
shape as the JSONL source rows.

This is not a forecast-behavior migration. Existing forecast commands remain file-backed by
default and unchanged; Phase 3 adds parity-proof scaffolding only.

## Decision

### Why only three source-domain tables

v59 adds exactly the minimum slice needed to prove read parity for core Tropical source
data, mapping 1:1 to the three canonical TWN cost-forecast JSONL sources consumed by the
context generator (`generate_forecast_context_package.py` `SRC_FILES`):

| v59 table | Source file (`<pkg>/data/`) | Rows (live pkg) |
|---|---|---|
| `forecast_budget_details` | `budget_details.jsonl` | 127 |
| `forecast_cost_entries` | `cost_entries.jsonl` | 6324 |
| `forecast_monthly_actuals_by_budget_code` | `monthly_actuals_by_budget_code.jsonl` | 1081 |

The full forecast domain (operator/model controls, owner pay-app, staffing, schedule,
stage outputs, final-CSV source, recommendations) is deliberately **not** added — those
await later additive migrations once their projection/read requirements are concrete.

### raw_json parity strategy

Each table stores the **exact original JSONL row** in a `raw_json TEXT NOT NULL` column
(authoritative for parity) plus extracted key/lineage columns for indexing. The projection
never mutates the row before serializing it; `source_row_number` and the source
hash/path/run are projection-side lineage and live only in columns, never inside `raw_json`.

The DB read repositories (`read_budget_details_from_db`, `read_cost_entries_from_db`,
`read_monthly_actuals_from_db`) return `json.loads(raw_json)` and **nothing else** — no
lineage/index fields are merged into the returned dicts — so a parity test compares DB
output against the source JSONL by row shape. Reads are ordered by stable keys
(`budget_code_key`; `source_row_number`; `(budget_code_key, month, type)`); the parity check
itself is order-independent (normalized JSON multiset compare).

### Keys

- `forecast_budget_details`: `PRIMARY KEY (project_key, budget_code_key, source_package)` —
  `budget_code_key` is unique per BudgetDetails row.
- `forecast_cost_entries`: CostEntries has no natural business key, so a deterministic
  `cost_entry_id = fce-<sha256(project_key|source_package|source_row_number)[:32]>` is the PK,
  with `UNIQUE(project_key, source_package, source_row_number)` keeping re-projection
  idempotent without collapsing distinct rows.
- `forecast_monthly_actuals_by_budget_code`: **repo-truth correction** — the proposed
  4-tuple `(project_key, budget_code_key, month, source_package)` is extended to include
  `type` (`PRIMARY KEY (project_key, budget_code_key, month, type, source_package)`) so a
  `budget_code_key`/`month` carrying more than one row-type cannot silently collapse.

All three carry the recurring lineage columns: `project_key`, `source_package`,
`source_path`, `source_sha256`, `source_row_number`, `run_id` (nullable), `created_utc`,
`updated_utc`. Indexes cover `project_key`, `budget_code_key`, `source_package`, and `month`
(monthly actuals only).

### Projection boundaries

`source_domain_engine` / `source_domain_repository` / `source_reader` are new siblings of the
Phase 2 modules. They read the JSONL files as plain files and **do not import the
construction-financial-review Python package** (same boundary Phase 2 established). Required
identifiers are validated: BudgetDetails rows missing `budget_code_key` and monthly rows
missing `budget_code_key`/`month`/`type` are skipped with a warning rather than written with
NULL keys. The missing/blank source-hash fallback is deterministic
`sha256(package_name|source_path)` — never package-only — so two unhashable files never
collapse to one lineage value.

### Dry-run / apply / live-DB safety

- Dry-run (default) plans rows from files and **never opens the DB**.
- `--apply` requires an explicit `--db-path` (`reason=apply_requires_explicit_db_path`).
- `--apply` additionally **refuses any path that resolves to the live/default DB**
  (`PathPolicy().get_db_path()`, `reason=apply_refuses_live_db`) — stronger than Phase 2,
  which only required an explicit path. If path resolution raises, `is_live_db_path` returns
  `True` (fails closed) so an unresolvable path is never written.
- `--parity` proves DB↔JSONL round-trip only **after** a successful apply to an explicit temp
  DB; requested without `--apply` it **fails closed** (`reason=parity_requires_applied_db`)
  rather than implying parity was proven.

Writes go through transaction-wrapped idempotent UPSERTs (`_IMMUTABLE={"created_utc"}`).

### CLI

`construction-agent forecast source-domain --project … --source-package … [--db-path …]
[--run-id …] [--apply] [--parity] [--json]`, mirroring `forecast project`. Default dry-run
writes nothing; the JSON receipt reports planned/written counts per table, source hashes,
row counts, and parity status when requested.

## Relationship to other phases

- **Phase 2 (ADR 258):** unchanged. Lineage projection and the v58 foundation tables remain
  the system of record for run/package/source/validation lineage; v59 source rows reference
  the same `project_key`/`source_package`/`run_id`/`source_sha256` lineage conventions.
- **Phase 4/5 (future):** wiring existing forecast generators to read these tables, and
  replacing latest-glob/config-pin resolution, are out of scope here. v59 read repositories
  are parity-proof substrate for that work, not yet wired into any generator.

## `HB_FORECAST_DB_BACKED_READS` — deferred

The read toggle is **deferred to Phase 4/5** (confirmed with the operator). In Phase 3
parity is proven by calling the read repositories directly and by the `--parity` CLI path;
there is no non-speculative production consumer for a toggle yet, and the project forbids
dead/no-op toggle code. `read_json`/`read_jsonl` are untouched and no existing forecast
command reads from the DB. Phase 4 introduces the toggle when a real generator consumer
exists.

## Consequences

- `LATEST_SCHEMA_VERSION` 58 → 59; migration is additive (`CREATE TABLE IF NOT EXISTS`),
  idempotent, and records a single `schema_migrations` row for v59.
- Lifecycle contract `table_count` 384 → 387; the three tables are classified
  `forecast_source_domain_v59` / `operational_empty_expected` (empty until projection is
  applied). All 13 hardcoded `contract_table_count` assertions updated in lockstep.
- Existing forecast behavior, the live/default DB, and CFR source/config/package files are
  unchanged.
