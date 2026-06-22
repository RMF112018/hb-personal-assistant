# Runtime-Dependency Removal Backlog — Phase 1 Audit

**Status:** read-only audit deliverable. Companion to `package-dependency-map.md`.
**Date:** 2026-06-22

This backlog lists **only** the `runtime-input` and **dual-role** file dependencies — the
file I/O that must eventually move to the DB for forecasting to become DB-native and
DB-persistent. Pure `export`/`evidence`/`test-fixture`/`deprecated` artifacts are excluded
(they may stay file-based). Ordered by migration priority.

Legend — **DB status:**
- ✅ *path exists* — a DB-backed read/write already implemented (may be gated off / temp-only)
- 🟡 *table only* — schema table exists but no runtime read/write wired
- 🔴 *no DB home* — neither table nor code path exists

---

## P1 — Source-domain inputs (closest to done)

| # | Dependency | Stage | DB target | DB status | Action |
| --- | --- | --- | --- | --- | --- |
| 1 | TWN `budget_details` / `cost_entries` / `monthly_actuals` JSONL | context (Phase 6) | V59 `forecast_budget_details` / `forecast_cost_entries` / `forecast_monthly_actuals_by_budget_code` | ✅ via `db_source_adapter` (`HB_FORECAST_DB_BACKED_READS`, temp DB only, fail-closed on live) | Populate live source-domain rows under an authorized projection; flip the read toggle for live runs after parity. |

This is the only runtime input with a complete, verified file↔DB bridge. Remaining work is
**population + authorized live read**, not new plumbing.

## P2 — Other external inputs (no DB home)

| # | Dependency | Stage | DB target | DB status | Action |
| --- | --- | --- | --- | --- | --- |
| 2 | Owner pay-app JSONL (line items, totals, headers) | context | — | 🔴 | Define source-domain table(s) for owner pay-app; extend `_READERS`/adapter; project + parity. |
| 3 | Procore DB export JSONL (pay-app headers, line items, commitments) | context | — | 🔴 | Define source-domain table(s) for Procore export; extend adapter; project + parity. |

## P3 — Inter-stage package handoffs (the "shadow database")

These are dual-role: written by one stage, read as runtime input by the next via
`run_lineage.resolve_upstream`. They are the structural reason forecasts are not reproducible
from DB alone.

| # | Dependency | Producer → consumer | DB target | DB status | Action |
| --- | --- | --- | --- | --- | --- |
| 4 | `.cfr_run_state/full_fresh_<p>_<run_id>.json` (+ `current_<p>.json`) | run start → all stages | V58 `forecast_runs` (lineage foundation) | 🟡 (V58 tables exist, lineage read-model only; runtime resolution still file-based) | Make run/lineage resolution read from V58 instead of `.cfr_run_state`; retire `CFR_RUN_LINEAGE_STATE` file dependency for runtime resolution. |
| 5 | `forecast_context_package/.../canonical/*.jsonl` (full canonical set, incl. owner/procore mapped lines & commitments) | context → analysis + downstream | partly V59 (3 of the set); rest 🔴 | 🟡/🔴 | Persist the emitted canonical context as DB rows so analysis reads DB, not the package dir. Broader than the 3 source-domain tables. |
| 6 | `forecast_context_package/.../summaries/*` + `validation_report.json` + `manifest.json` | context → analysis + package-resolution gate | — | 🔴 | Persist context summaries + readiness/identity as DB rows; replace required-member file gate with a DB readiness check. |
| 7 | `forecast_analysis_package/.../forecast_recommendations_by_budget_code.jsonl` | analysis → downstream `forecast_*` | — | 🔴 **(no `forecast_output_*` table exists)** | **Key gap:** there is no forecast *output* table family. Define `forecast_output_*` (per remediation §9) and persist recommendations there; downstream reads DB. |
| 8 | `forecast_analysis_package/.../validation_report.json` + `manifest.json` | analysis → package-resolution gate | — | 🔴 | As #6, analysis-side. |
| 9 | `mapping_discrepancy_workpaper/.../*_crosswalk.jsonl` (if consumed downstream) | mapping → downstream | — | 🔴 | Confirm downstream consumption in pending sweep; persist crosswalks as DB rows if dual-role. |

## P4 — Config inputs

| # | Dependency | Stage | DB target | DB status | Action |
| --- | --- | --- | --- | --- | --- |
| 10 | `config/projects/<p>.json`, controls, model_controls, staffing mapping, `owner_sov_crosswalk` | all generators (via `CFR_CONFIG_ROOT`) | V60 `forecast_config_sources/items/snapshots/snapshot_items` | 🟡 — V60 exists; current DB-config path *re-materializes a snapshot back to files* and points `CFR_CONFIG_ROOT` at it (file bridge, not direct DB read at generate time) | Have generators read config from a V60 snapshot directly (or treat the materialized bridge as the cutover seam); remove the file-materialization round-trip once parity holds. |

## P5 — Read-model (Surface B) inputs

| # | Dependency | Component | DB status | Action |
| --- | --- | --- | --- | --- |
| 11 | Package manifests + `.cfr_run_state` read by `forecast/package_reader.py`, `run_reader.py`, and most `/api/forecast/*` package-detail routes | hb_assistant API | 🟡 (V58/V60 used for runs/config; package detail still file-sourced) | Once P3 output tables exist, repoint the API package-detail endpoints at DB reads. |

---

## Cross-cutting gaps (no DB home today)

1. **No forecast-output table family.** The schema has lineage (V58), source-domain (V59),
   config (V60), external-eval (V61), and schedule (V62) tables — but **no** `forecast_output_*`
   tables for the model's own recommendations / monthly curve / probability / risk outputs.
   Items #5–#8 cannot fully land until this family is designed (remediation §9.1).
2. **Run lineage is file-resident at runtime.** V58 `forecast_runs` exists as a read-model,
   but runtime upstream resolution still depends on `.cfr_run_state` files (#4).
3. **Owner pay-app & Procore export have no source-domain tables** (#2, #3) — only TWN does.
4. **Config DB path is a file round-trip**, not a direct DB read (#10).

## Suggested sequencing (input to later phases — not part of this audit)

1. Land item #1 (source-domain population + authorized live read) — lowest risk, plumbing exists.
2. Add owner/Procore source-domain tables (#2, #3).
3. **Design the `forecast_output_*` table family** (unblocks #5–#8).
4. Move run lineage to V58 (#4), then persist context/analysis to DB (#5–#8).
5. Direct V60 config reads (#10); repoint read-model API (#11).

All cutovers must preserve the existing fail-closed / authorized-live-write discipline
(temp-DB rehearsal → certification → gated operator run) already established in `workflows/`.
