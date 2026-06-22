# ADR 285 — Forecast Phase 2a: run-output schema (V63) + read-only projector

## Status

Accepted.

## Context

The Phase-1 package-dependency audit (PR #86,
`docs/evidence/forecast-phase1-package-dependency-audit/`) identified the keystone gap in the
forecasting DB-native remediation: there was **no `forecast_output_*` table family**. The
schema held lineage (V58), source-domain (V59), config (V60), external-eval (V61), and schedule
(V62) tables, but the model's own results lived only in CFR's
`forecast_analysis_package/.../forecast_recommendations_by_budget_code.jsonl` and sibling files
— a dual-role "shadow database". The V58 `forecast_runs` table is lineage-only
(`run_id, project_key, context_package, status, notes, created_utc`) and cannot host outputs.

## Decision

Add the run-output schema as **V63** and a **read-only projector** that proves the schema fits
real analysis-package data, writing into a temp DB only — never the live DB.

### Schema (V63, family `forecast_output_v63`, all `operational_empty_expected`)

10 additive tables in `src/hb_assistant/store/forecast_output_tables.py`, wired via
`SQLiteMigrator._v63_statements()` (mirrors the V62 large-set pattern):

- `forecast_outputs` — per-run header; FK `run_id` → `forecast_runs(run_id)`.
- children FK `output_id` → `forecast_outputs(output_id)`: `forecast_output_budget_codes`,
  `forecast_output_monthly`, `forecast_output_probability`, `forecast_output_risks`,
  `forecast_output_changes`, `forecast_output_commitment_exposure`, `forecast_output_staffing`,
  `forecast_output_schedule_phasing`, `forecast_output_narratives`.

Column style mirrors V59: TEXT deterministic PKs, money as TEXT (Decimal strings, never
floats), `raw_json TEXT NOT NULL` as the authoritative row, `created_utc`/`updated_utc`,
`idx_<table>_<col>` indices. `table_count` 412 → **422**.

**Scope split from V61.** This family is for **model runs** (FK to `forecast_runs`) and is
distinct from V61's external-forecast-evaluation tables, which evaluate operator-supplied
forecasts (`forecast_anomaly_findings`, `forecast_review_items`, `forecast_evidence_packages`).
No table-name collisions; the model-run anomaly/review/evidence equivalents are deferred to a
later phase and will be named to disambiguate.

### Projector (read-only, temp-DB only)

`src/hb_assistant/construction/forecast/output_projection_engine.py` +
`output_repository.py`, mirroring the v59 `source_domain_engine`/`source_domain_repository`:

- `plan_run_output_projection` builds planned rows from an **explicit** analysis-package dir
  read as plain JSON — no DB access, no CFR import, no latest-glob.
- `project_run_output` returns the plan for a dry-run, or writes it in a single transaction
  (idempotent UPSERTs) for `apply`, with optional canonical read-parity.
- `apply` requires an explicit `db_path` and **refuses** `PathPolicy().get_db_path()`
  (fail-closed on resolve error), reusing `is_live_db_path`.

**Coverage this phase** (analysis package is the only source read): `forecast_outputs` header,
`forecast_output_budget_codes` (from `forecast_recommendations_by_budget_code.jsonl`), and
`forecast_output_risks` (from `forecast_risk_register.jsonl`). The remaining 6 tables ship empty
— their sources are downstream packages (monthly/probability/comprehensive), deferred to a
follow-on slice, mirroring V59's "slice" discipline.

## Consequences

- The DB can now host model-run outputs; unblocks audit backlog P3 #5–#8.
- No behavioral change: forecast runtime reads stay file-backed; live DB is never written.
- Lifecycle bookkeeping: `table_count` and ~18 hardcoded count asserts bumped 412 → 422; the
  exact-version `== 62` asserts relaxed/retargeted to `LATEST_SCHEMA_VERSION`.
- `store/` is excluded from ruff/mypy; the projector modules under `construction/forecast/`
  follow the existing engine style.

## Verification

- `tests/test_migrator_v63_forecast_outputs.py` — version, presence, empty, idempotency,
  prior-version preservation, FK, lifecycle classification.
- `tests/test_forecast_output_projection_phase2a.py` — plan-without-DB, dry-run touches no DB,
  parity-fails-closed-on-dry-run, apply-requires-db-path, apply-refuses-live-DB, apply writes
  with canonical parity and is idempotent.
