# 256 — Forecast JSON/JSONL → SQLite Transition (Schema Ownership)

Status: Accepted (Phase 1 foundation landed; domain phases pending)
Date: 2026-06-17
Related: ADR 255 (Procore Budget Detail Rows read model), `local_audit_outputs/db_transition_plan_inputs_20260617_163622/` evidence package.

## Context

The Tropical `construction-financial-review` (CFR) forecasting workflow reads its
inputs from timestamped JSON/JSONL package directories and in-repo operator
control/crosswalk files, discovered via `_latest_dir()` globs and config pins. The
local SQLite DB already holds the upstream Procore data in populated read-model
tables (`procore_ep_budget_detail_*`, `procore_financial_*`) but holds none of the
forecast-generated outputs, operator controls, or upstream TWN/owner extracts. The
goal is to make SQLite the authoritative local forecast data source without breaking
the existing JSON workflows until DB parity and validation are proven.

## Decision

**Forecast-native DB tables live in `hb_assistant/store/migrator.py` as additive,
version-gated migrations** under the unified `schema_migrations` ledger — not in a
CFR-specific migration layer. Rationale: v55–v57 (the Procore Budget Detail read
model) already live in the hb_assistant migrator; CFR is a pure read-only consumer
(`procore_budget_details_db.py` opens `mode=ro`, no `hb_assistant.store` import);
unified versioning keeps one source of truth. A CFR-specific layer is reconsidered
only if a hard technical blocker appears.

**Migrations are foundation-first.** The first transition migration (**v58**) lands
ONLY the five lineage/foundation tables — `forecast_projects`, `forecast_runs`,
`forecast_source_ingestions`, `forecast_package_manifests`, `forecast_validation_events`.
Downstream forecast-domain tables (budget/cost/owner canonical data, operator
controls, schedule/staffing, forecast stage outputs, final-CSV source) are deferred
to later additive migrations (v59+) once projection and read-repository requirements
are concrete. v58 exists to prove ownership, idempotency, and lineage conventions.

## Access policy

- Reads: standalone `connect_read_only(...?mode=ro)` + `PRAGMA query_only=ON` (no
  `hb_assistant.store` dependency on the read path).
- Schema DDL: only the hb_assistant migrator (additive).
- Data writes (later phases): a single dedicated transactional writer, scoped to
  forecast-owned tables; never mutates `procore_*` / hb_assistant core tables.

## Consequences / follow-ups

- New forecast tables must be registered in `resources/json/table_lifecycle_status_contract.json`.
  NOTE: that contract is already stale on `main` (32 tables present in a fully
  migrated DB are absent from the contract; v58 adds 5 → 37). Registering the
  forecast tables (and reconciling the broader backlog) is a tracked follow-up, not
  part of the v58 foundation migration.
- The budget-code CSV ↔ recommendations reconciliation gap (−$3.42M) is a hard
  Phase‑9 gate; see the evidence package `gap_classification.md`.
- Validation interpreter should standardize on Python 3.12 + pinned deps once
  network access permits provisioning the venv.
