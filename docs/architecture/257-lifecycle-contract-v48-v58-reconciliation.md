# 257 — Table-Lifecycle Contract Reconciliation (v49–v58 backlog)

Status: Accepted
Date: 2026-06-17
Related: ADR 256 (Forecast JSON/JSONL → SQLite Transition), ADR 241 (Procore endpoint-specific structured projection), `src/hb_assistant/construction/data_quality/table_inventory.py`.

## Context

The canonical `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` is the single
source of truth consumed by `construction-agent data-quality table-inventory`
(`build_table_inventory_report`). It reconciles the live SQLite schema against the contract and reports
`in_db_not_in_contract`; roughly a dozen schema-version tests assert that list is `[]` and that
`contract_table_count == 347`.

The contract had drifted: tables added in migrations **V49–V55** were never registered, and PR #29
(ADR 256, merge `d40ff03c`) added five **V58** forecast foundation tables but explicitly deferred their
registration. A read-only diff against the live store (schema v57, 379 user tables; `immutable=1`) showed
`in_db_not_in_contract` = **exactly 32** tables and `in_contract_not_in_db` = **0**. With the five v58
tables this is a **37-table backlog**, leaving ~11 lifecycle reconciliation tests red on `main`. (Two
earlier static-source estimates — 24 and 5 — were wrong: the V47 `procore_ep_*` and V49 email/calendar
tables are created via generated/registry DDL such as `build_v49_ddl`, not literal `CREATE TABLE`
string-literals, so a migrator text scan undercounts. The live-DB diff is authoritative.)

## Decision

Register all **37** tables in one reviewed change and bump `table_count` **347 → 384**. Classification
follows existing sibling-family convention and **actual live population**:

- **V49 email/calendar structured projection (13)** — family `email_calendar_structured_v49`. The ten
  populated tables (`email_raw_*`, `calendar_raw_event_*`, `email_calendar_projection_runs/coverage`) →
  `operational_populated`; the three empty operational ledgers
  (`calendar_raw_event_recurrence_structured`, `email_calendar_raw_ingestion_runs`,
  `raw_content_source_quality_snapshots`) → `operational_empty_expected`.
- **V55 Procore endpoint budget-detail (3)** — family `procore_ep_budget_detail_v55`,
  `operational_populated` (populated from the budget-detail read model; rows/cells/columns).
- **V50–V54 Phase 10 daily-brief / candidate / ranking (16)** — `placeholder_deferred` / phase_owner
  `10`, matching the existing `phase10_*_v41` siblings; all currently empty, populated by later Phase 10 work.
- **V58 forecast foundation (5)** — family `forecast_foundation_v58`, phase_owner `forecast_db_transition`,
  **`operational_empty_expected`** with `expected_population_status: "empty"`. These are real, tested
  foundation schema that intentionally ship empty until Phase 2+ writes run/ingestion/manifest/validation
  records; they are **not** speculative placeholders. The "empty until Phase 2+" semantics live in each
  entry's `notes` rather than as a new `expected_population_status` value, keeping the field within its
  established `empty`/`populated` vocabulary.

The 13 hardcoded `contract_table_count == 347` assertions across the schema-version and data-quality-gate
tests are updated to `384` in lockstep.

## Consequences

- `in_db_not_in_contract` returns `[]` against the live store; the previously-red reconciliation tests go
  green. The five v58 tables sit in `in_contract_not_in_db` until v58 is applied to the live DB — tolerated
  (no test asserts that list empty), matching the v58 "ships empty / future population" posture.
- `report["tables"]` and `summary_by_status` are built from live tables only, so contract-only entries do
  not perturb the `sum(summary_by_status) == len(tables)` invariant.
- Scope is contract data + its count assertions only: no schema change, no projection logic, no forecast
  behavior change, and the v58 migrator was **not** run against the live DB (it remains at v57). ADR 241's
  point-in-time "`table_count` stays 347" note is superseded by this record rather than rewritten.

## Method (reproducible, read-only)

Diff `live_set` (sqlite_master tables/views, `sqlite_%` excluded, opened `immutable=1`) against the
contract `tables` keys; classify each backlog table by its introducing migration version and its actual
live row count. Future migrations must register new tables in the contract atomically with the migration.
