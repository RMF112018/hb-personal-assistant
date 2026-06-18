# 258 — Forecast Phase 2: JSON/JSONL → SQLite Lineage Projection

Status: Accepted
Date: 2026-06-17
Related: ADR 256 (Forecast DB Transition — schema ownership), ADR 257 (lifecycle-contract reconciliation),
`src/hb_assistant/construction/forecast/`.

## Context

ADR 256 landed the **v58** foundation schema — five lineage tables — but nothing populated them. The CFR
forecast workflow resolves runs via `_latest_dir()` globs / config pins / `.cfr_run_state`, then reads
timestamped JSON/JSONL package directories. Phase 2 builds the **projection + dry-run infrastructure** that
records a completed run's lineage into the v58 tables, so the DB can answer "which exact packages, sources,
hashes, and validations formed this run?" — the substrate for Phase 4 replacing latest-glob/config-pin
ambiguity with a single DB-backed run-lineage source.

## Decision

A new `hb_assistant` module package `src/hb_assistant/construction/forecast/` projects a **forecast run
(parent)** and its **packages (children)** into the five v58 tables. The schema-owning write code lives in
`hb_assistant` (per ADR 256); CFR stays a read-only consumer. The engine reads `.cfr_run_state` and package
`manifest.json` / `input_inventory.json` / `validation_report.json` as **plain JSON — it does not import the
construction-financial-review package** (keeps `hb_assistant` decoupled from the subrepo).

**Lineage only.** Phase 2 projects identity/run/source/manifest/validation metadata. It does **not** project
domain rows (monthly values, recommendations, cost entries, BudgetDetails, owner pay-app, operator/model/
staffing controls) — those await v59+ domain tables. **No new schema.** **No forecast read-path change** —
forecast model reads remain file-backed by construction (no flag added).

### Modules

- `run_reader.py` — resolve `.cfr_run_state/current_<project>.json` → active
  `full_fresh_<project>_<run_id>.json`; yield `run_id`, `project_key`, `run_started_at_utc`, and packages
  (`ptype -> {path, stamp}`).
- `package_reader.py` — defensive parse of one package's `manifest.json`
  (`package_name`, `generated_stamp`, `project{name,project_key,job}`, `output_files[]`, `source_files[]`,
  `validation_status{gate:bool}`, `conclusion`); missing keys degrade into `warnings`, never raise.
- `projection_engine.py` — `plan_run(...)` builds planned rows **purely from files (no DB)**;
  `project_run(..., apply=False)` returns that plan for a dry-run, `apply=True` writes it in one transaction.
- `repository.py` — idempotent `INSERT ... ON CONFLICT(<key>) DO UPDATE` upserts on the tables' existing
  keys.

### Source → v58 table mapping

| Table | Cardinality | Source |
|---|---|---|
| `forecast_projects` | 1 / run | manifest `project` block (`project_key`, `name`→project_name, `job`→job_number) |
| `forecast_runs` | 1 / run | run-state `run_id`/`project_key`/`run_started_at_utc`; `context_package` = pinned context package name |
| `forecast_package_manifests` | 1 / package | manifest (`package_type`, name, stamp, `upstream_packages`, `source_data_hashes`, `row_counts`, `validation_passed`, `conclusion`, `file_path`) |
| `forecast_source_ingestions` | N / package | manifest `source_files[]` (`source_kind`=label, `source_path`, `source_sha256`, `row_count`) |
| `forecast_validation_events` | M / package | manifest `validation_status{gate:bool}` → one event per gate; `gate_name` is package-type-prefixed |

### Idempotency

Deterministic surrogate IDs via sha256: `ingestion_id = fsi-<hash(project_key|source_package|source_sha256)>`,
`package_id = fpm-<hash(project_key|package_name)>`. Upsert keys: `project_key`; `run_id`;
`(project_key, source_package, source_sha256)` (via the deterministic `ingestion_id` PK); `package_name`
(via `package_id`); `(run_id, event_seq)`. `event_seq` is a monotonic counter assigned over a **stable
package order (by stamp, then ptype) then gate order**, so re-projecting a fixed run lands the same rows.
`created_utc` and key columns are never overwritten. Re-running `apply` upserts, never duplicates.

**NULL-sha guard.** SQLite treats NULLs as distinct, which would break the `(project_key, source_package,
source_sha256)` UNIQUE. When `source_files` lacks a sha, the reader derives a deterministic
`sha = hash(package_name | source_path)` — **never package-only** — so two sha-less sources with different
paths stay distinct while re-runs still dedup.

### Safety

Dry-run (default) **never opens the DB**. `--apply` **requires an explicit `--db-path`** and refuses the
default/live DB (`reason: apply_requires_explicit_db_path`) — Phase 2 applies only to temp v58 DBs. The
live DB remains v57; applying v58 to it is a separate, explicitly-authorized action.

## CLI

`hb-assistant construction-agent forecast project --project tropical [--run-state PATH]
[--subproject-root PATH] [--db-path PATH] [--apply] [--json]` — dry-run default; emits a JSON receipt with
planned/written counts, per-package detail, warnings, and guardrails.

## Validation

`tests/test_forecast_projection_phase2.py` (synthetic run-state + 2 packages, temp v58 DB): dry-run writes
nothing; apply requires `--db-path`; apply writes all five tables; apply-twice is idempotent; the two
sha-less sources stay distinct; pointer-based resolution works; `event_seq` is stable and prefixed. A
read-only dry-run smoke against the live active run (`20260617_152650`) parsed 4 packages → 1/1/4/46/17 rows
with zero warnings, writing nothing. mypy + ruff clean.

## Future (Phase 3+, not in Phase 2)

- **DB-backed reads** behind a default-off `HB_FORECAST_DB_BACKED_READS` env toggle (mirroring
  `procore/live_gate.py`) — deferred until v59+ domain tables exist to serve forecast data.
- **v59+ domain tables** for per-code monthly/probability/evidence/operator-control rows.
- Relaxing the `--apply` `--db-path` requirement once live-DB migration is authorized.
