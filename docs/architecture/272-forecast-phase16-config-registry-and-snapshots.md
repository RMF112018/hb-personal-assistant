# ADR 272 — Forecast Phase 16: config registry, snapshots & DB-backed config wiring

- **Status:** Accepted
- **Date:** 2026-06-19
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 16
- **Builds on:** ADR 258–271 (Phases 2–15); v58 (PR #29), lifecycle contract (PR #30), Phases 2–15 (PRs #31–#44, Phase 15 merge `2ec8b0b7`).

## Context

The operator-approved forecast config — project settings, forecast controls, model controls, staffing
mappings, and the authoritative owner-SOV crosswalk — lives in repo files under
`subrepos/construction-financial-review/config/`. This is governed project decision data (effective-dated,
operator-accepted), not static app config, and belongs in a DB that can be snapshotted, hashed, and
traced. Phase 16 builds a governed SQLite **forecast config registry** (schema **v60**), with
import/export/snapshot/materialize tooling, and makes DB-backed config a real reader input — **without**
flipping any default and **without** running any out-of-scope generator.

### Decisive repo-truth finding

An exhaustive config-reader audit established that the **controlled context→analysis chain (Phase 6→7→9→
12→15) reads NONE of the operator config**: the context generator reads only source data (its "crosswalk"
output is computed, not read); the analysis generator reads zero config. Operator config is consumed only
by the **out-of-scope** downstream generators (`forecast_monthly/comprehensive/cost_frequency/
staffing_plan/model_controls`) + `forecast_probability`, **and** by the **in-scope, deterministic,
non-LLM** `validate-crosswalk`. Config root is resolved from a hardcoded `SUBPROJECT_ROOT` with no
override hook.

Therefore Phase 16 does **not** fake config-dependence in the controlled chain. It proves the registry at
the **reader layer** + the **`validate-crosswalk`** consumer, and carries config-snapshot evidence through
Phase 9/12/15 reports as **lineage-only metadata** explicitly labeled not-consumed.

## Decision

### Schema (v60) — `hb_assistant` migrator + lifecycle contract (schema-only change)

`LATEST_SCHEMA_VERSION` 59 → **60**; `V60_STATEMENTS` adds four additive tables
(`forecast_config_sources`, `forecast_config_items`, `forecast_config_snapshots`,
`forecast_config_snapshot_items`) + indexes, registered as `v60_forecast_config_registry` (idempotent;
`CREATE TABLE IF NOT EXISTS`). Tables store raw + canonical JSON, preserve row order (`item_order`), carry
effective/status metadata (no UI in this phase), and keep re-import/snapshot idempotent via UNIQUE/PK.
Lifecycle `table_count` 387 → **391** with four `forecast_config_registry_v60` /
`operational_empty_expected` entries. The 14 current/global contract-count assertions were classified
(all read the live contract via `build_table_inventory_report` / the contract JSON, none a historical
per-version count) and bumped to 391 with a Phase 16 comment. The optional `forecast_project_config_values`
normalization table is **deferred** (project JSON is kept as a normal config item).

Because the migrator's latest version moved to v60, the Phase 14 backup / pre-write schema checks were
loosened from exact `!= 59` to `< 59` (accept v59+) — aligning Phase 14 with the `>= REQUIRED_SCHEMA_VERSION`
convention the other phases already use; `REQUIRED_SCHEMA_VERSION` stays 59 (the minimum carrying the v59
source-domain tables). Migrated-DB schema-version test literals were updated 59 → 60.

### CFR config registry module `config_registry.py`

`import_forecast_config_to_db`, `export_forecast_config_from_db`, `create_forecast_config_snapshot`,
`materialize_forecast_config_snapshot`, plus `run_forecast_config_db_parity`, `resolve_forecast_config`
(`ForecastConfigResolution`), and `config_snapshot_lineage_block`. Direct `sqlite3` writes with a lazy
`SQLiteMigrator` for non-live temp DBs; `hb_assistant` is imported lazily and the source-domain
`is_live_db_path` guard is reused (live import requires `allow_live_db_write=True`; never run against the
real DB in impl/tests). Parsing: JSON → 1 item; JSONL → 1 item/nonblank line (order preserved); CSV → 1
item/row (order preserved); invalid JSON/CSV fail closed with file + line/row; duplicate item-keys within a
source fail closed. Deterministic per-domain item-key derivation (project_key / control_id / source_cost_code|
target / crosswalk_id / else row index). Export and materialize emit deterministic file-compatible trees +
manifests (no wall-clock in hashed fields). Snapshots are immutable (active items, content-hashed).

### Opt-in `CFR_CONFIG_ROOT` bridge (`common/config_root.py`)

A single, explicit, opt-in override read inside the existing path-resolution helpers (`load_controls`/
`load_model_controls` `control_file_path`, `load_mapping` `mapping_file_path`, `cli.load_project`,
`cli._resolve_crosswalk`). **Unset → byte-identical current behavior** (hardcoded `SUBPROJECT_ROOT`); **set
→ an existing absolute directory** (else fail closed). DB-backed config becomes a real reader input by
materializing a snapshot to a file-compatible root and pointing `CFR_CONFIG_ROOT` at it inside controlled
execution (scoped, try/finally restored). It is never a production default and never set globally.

### `validate-crosswalk` (the one in-scope deterministic consumer) + additive CLI

`validate-crosswalk` gains `--config-source file|db_snapshot` (+ `--config-db-path/--config-snapshot-id/
--config-snapshot-root`): db_snapshot materializes the snapshot under the work root, points
`CFR_CONFIG_ROOT` at it (scoped), runs the existing resolver/validator, and proves file-vs-DB parity (rc 0
pass / rc 1 mismatch). New additive commands: `forecast-config-import`, `forecast-config-snapshot`,
`forecast-config-export`, `forecast-config-db-parity` (rc 0 success/pass, 1 not-ready/mismatch, 3 refusal).
All existing commands unchanged (additive parser/handler/dispatch; cli.py not ruff-format-enforced).

### Phase 9/12/15 lineage metadata only

Each gains an optional `config_snapshot_root`; when provided, the report carries a `config_snapshot` block
with `config_snapshot_consumed: false`, `config_snapshot_attached_for_lineage: true`,
`config_consuming_components: []`,
`config_not_consumed_reason: "Phase 6/7/9/12/15 controlled chain does not read operator config per
repo-truth audit"` + snapshot id / manifest / row counts / hashes. Default `None` → no report change. The
snapshot is never an execution dependency for these phases.

## Parity strategy

Reader-layer parity: import the repo config → snapshot → materialize → for each domain compare the records
the readers would parse from the repo base vs the materialized snapshot (identical after no normalization is
needed). On the real config: 6 sources / 194 items, parity **pass** for all domains; `validate-crosswalk`
file vs DB-snapshot **pass**. Mismatch fails closed (rc 1) with exact differing domains.

## Operator path (deferred — not run in implementation/testing)

A separate authorized operator action will: migrate the live DB to v60; import current config; create a
snapshot; run DB-snapshot-backed `validate-crosswalk`; prove parity; only then consider any default change
in a later phase. Implementation/tests used synthetic config + synthetic temp DBs; the real live DB and the
real config folder were never written.

## Consequences

- Governed, importable/exportable/snapshottable/materializable forecast config, with a faithful reader-layer
  bridge and a real in-scope consumer (`validate-crosswalk`), and lineage-only evidence through the
  controlled chain — no false claim that Phase 6/7/9/12/15 consume config.
- Additive schema only; `LATEST_SCHEMA_VERSION` 60; lifecycle table count 391; no production default flip;
  file-backed config remains the default and is fully tested.

## Deferred (unchanged by Phase 16)

- Live DB migration/import (operator action); DB-backed config as a production default.
- `forecast_project_config_values` normalization table; UI editing.
- Wiring DB-backed config into the downstream config-consuming generators
  (`forecast_comprehensive/monthly/probability`); model-backed/LLM/intelligence workflows; integrated CSV.
- v58 `forecast_package_manifests` DB resolver; the −$3.42M reconciliation; Phase 17.
