# Forecasting Package-Dependency Map — Phase 1 Audit

**Status:** read-only audit (no source/config/DB changes). Deliverable artifact only.
**Date:** 2026-06-22

## Provenance

| Repo | Branch | Commit |
| --- | --- | --- |
| `hb-personal-assistant` | `feature/forecast-ui-live-config-promotion-orphan-fix` | `33fd116ca9438eb84437686b84494c1f8ade83db` |
| CFR (`subrepos/construction-financial-review`) | (same repo) | `33fd116…` |

**CFR is vendored in-tree, not a submodule.** There is no `.gitmodules` and no nested
`.git`; `subrepos/construction-financial-review/**` is tracked directly in the
`hb-personal-assistant` git tree (verified: `git ls-files` lists `…/cli.py`). So the CFR
source commit *is* the hb_assistant commit `33fd116…`. The empty standalone
`/Users/bobbyfetting/construction-financial-review` clone (`origin/main 644a25d…`) is a
separate stale checkout and is **out of scope**.

CFR observed size: **181 non-test Python modules** under `src/` (verified by `find`), 106 tests.

## Purpose & taxonomy

Separate file I/O that is a **runtime input** to a forecast stage (must eventually move to
the DB) from pure **outputs** (export / evidence) that can remain file-based. Each entry
has one primary role plus a **dual-role** flag.

| Primary role | Meaning |
| --- | --- |
| `runtime-input` | Read as input to a forecast stage; must migrate to DB |
| `export` | Human-readable output (README.md, SCHEMA.md, `top_*` summaries) |
| `evidence` | Audit / lineage output (`audit/*.json`, mapping trails, gap/risk registers) |
| `test-fixture` | Used only by tests / `examples/` |
| `deprecated` | Stale package, no `validation_report.json`, unused |

**Dual-role (critical):** artifacts *written* by one stage and *read as runtime input* by a
later stage — the "shadow database" core and the highest-priority removal targets.

> **Methodology note.** This inventory was assembled from a systematic module-level
> exploration of CFR, **direct source verification** of the four load-bearing mechanisms
> (`db_source_adapter.py`, `common/run_lineage.py`, `common/package_resolution.py`, the
> context generator's source-row load path), and a **completed mechanical `grep` sweep**
> across all 181 non-test modules. See the call-site census below and `audit-method.md`.

## Call-site census (CFR `src/`, non-test, verified by grep)

| Pattern | Count | Pattern | Count |
| --- | --- | --- | --- |
| `open(` | 41 | `write_jsonl` | 120 |
| `json.load` | 36 | `write_json` | 310 |
| `read_jsonl` | 168 | `write_text` | 58 |
| `read_json` | 230 | `shutil.copy2` | 11 |
| `.glob(` | 21 | `def emit_` | 13 (all in the context generator) |
| `.rglob(` | 63 | `def resolve_inputs` | 3 |
| `.iterdir(` | 3 | `resolve_upstream` (callers) | 7 |

Two distinct **runtime-input discovery** mechanisms exist (both are latest-glob / package
discovery and both make packages a shadow database):
1. `common/run_lineage.resolve_upstream` — used by `analysis/generate_forecast_analysis_package.py`,
   `analysis/generate_forecast_analysis_crosswalk_v2.py`, `mapping/generate_mapping_discrepancy_workpaper.py`.
2. **Per-domain package discovery** — `forecast_comprehensive/package_discovery.py`,
   `forecast_staffing_plan/package_discovery.py`, and `*_io.py` readers
   (`forecast_cost_frequency/frequency_io.py`, `forecast_history_informed/history_io.py`,
   `schedule_analysis/schedule_io.py`) plus glob in `forecast_accuracy`, `forecast_intelligence`,
   `forecast_monthly`, `forecast_controls`, `forecast_model_controls`. The downstream generators
   discover their upstream packages **themselves**, not via `resolve_upstream`.

---

## Surface A — CFR producer pipeline (primary)

Package root: `subrepos/construction-financial-review/src/construction_financial_review/`

### A1. External input sources (RUNTIME INPUTS — the pipeline's true inputs)

Read by the context generator (Phase 6). These are the genuine upstream inputs.

| Source | Path pattern | Role | Target DB | Notes |
| --- | --- | --- | --- | --- |
| TWN cost forecast | `twn_cost_forecast_json_package/data/*.jsonl` (budget_details, cost_entries, monthly_actuals_by_budget_code) | `runtime-input` | V59 `forecast_budget_details` / `forecast_cost_entries` / `forecast_monthly_actuals_by_budget_code` | DB path exists via adapter (A2) |
| Owner pay-app | `owner_pay_app_json_package/*.jsonl` (line items, totals, headers) | `runtime-input` | **no DB table yet** | gap |
| Procore DB export | `cost_forecast_agent_db_json_export_tropical_*` (pay-app headers, line items, commitments) | `runtime-input` | **no DB table yet** | gap |

### A2. Source-row read adapter (file ↔ DB) — VERIFIED

`context/db_source_adapter.py`

| Symbol | Reads | Role | Notes |
| --- | --- | --- | --- |
| `db_backed_reads_active()` | env `HB_FORECAST_DB_BACKED_READS == "1"` | toggle | default off → file-backed |
| `load_forecast_source_rows(...)` | JSONL via `read_jsonl_fn` (default) **or** DB (toggle on) | `runtime-input` provider | source-file order preserved |
| `_read_from_db(...)` | `HB_FORECAST_DB_PATH` SQLite via lazy `hb_assistant.construction.forecast.source_domain_repository` | `runtime-input` | fail-closed: refuses live DB (`is_live_db_path`), unset path, import failure, empty rows |
| `_READERS` | `budget_details`→`read_budget_details_in_file_order`, `cost_entries`→`read_cost_entries_in_file_order`, `monthly_actuals`→`read_monthly_actuals_in_file_order` | mapping | the 3 source-domain → V59 readers |

This is the **only** existing file→DB runtime-input bridge today, and it covers only the
three TWN source-domain reads.

### A3. Lineage & package discovery (RUNTIME-INPUT discovery) — VERIFIED

| File:symbol | Reads | Role | Dual-role | Notes |
| --- | --- | --- | --- | --- |
| `common/run_lineage.py:active_state_path/active_state/load_state` | env `CFR_RUN_LINEAGE_STATE` → `.cfr_run_state/full_fresh_<project>_<run_id>.json` | `runtime-input` | yes | run-state file is written by the run and read by every downstream stage |
| `common/run_lineage.py:resolve_upstream` | precedence: explicit override → active run state → latest-glob | `runtime-input` discovery | — | fail-closed; resolves which context/analysis package a stage consumes |
| `common/run_lineage.py:record_latest/_latest_of` | `glob(<prefix>_<project>_*)` package dirs under `data_root`; validates stamp ≥ run_id + `validation_report.json` | `runtime-input` discovery | — | latest-glob fallback when no active state |
| `common/package_resolution.py:resolve_explicit_package` | explicit package dir; validates required members | `runtime-input` validation | — | members: context = `manifest.json`,`validation_report.json`,`canonical`,`summaries`; analysis = `manifest.json`,`validation_report.json`,`forecast_recommendations_by_budget_code.jsonl` |
| `common/package_resolution.py:read_package_chain_manifest` | chain manifest JSON (schema v1) | `runtime-input` | — | deterministic; explicit only, never latest-glob |
| `common/package_resolution.py:write_package_chain_manifest/build_package_chain` | writes chain manifest | `evidence` | — | controlled-run lineage record |
| `common/config_root.py:config_root_override/resolve_config_base` | env `CFR_CONFIG_ROOT` | `runtime-input` discovery | — | routes config base to a materialized snapshot (A7) |
| `common/io.py:read_json/write_json` | generic JSON read/write helper | (helper) | — | underlies most readers/writers |

### A4. Context generator (Phase 6) — `context/generate_forecast_context_package.py`

Reader side (`resolve_inputs`, `_load_inputs_and_index`, `read_jsonl`, `read_json`) →
classified under A1/A2. Writer side (`emit_*`, `build_context_package`) emits
`forecast_context_package_<project>_<stamp>/`:

| Output member | Writer | Role | Dual-role |
| --- | --- | --- | --- |
| `canonical/budget_codes.jsonl`, `cost_entries.jsonl`, `monthly_actuals_by_budget_code.jsonl`, `owner_pay_app_*`, `procore_*`, `procore_commitments.jsonl` | `emit_*` → `write_jsonl` | durable forecast record | **yes** — read by analysis (A5) & downstream (A9) |
| `summaries/budget_code_forecast_context.jsonl`, `summaries/project_forecast_context.json` | `emit_budget_code_summary` / `emit_project_summary` | durable forecast record | **yes** — read by analysis |
| `mapping/owner_cost_code_family_crosswalk.jsonl` | `emit_owner_family_crosswalk` | durable forecast record | **yes** — read by analysis |
| `mapping/owner_pay_app_mapping_results.jsonl`, `unmapped_*`, `ambiguous_mapping_candidates.jsonl` | `emit_owner_line_items` | `evidence` | — |
| `summaries/mapping_coverage_summary.json`, `data_gap_register.json` | (load/validation) | `evidence` | partially read by analysis |
| `audit/reconciliation_report.json`, `source_files_used.json`, `source_validation_snapshot.json`, `safety_scan_report.json` | (validation) | `evidence` | reconciliation/validation read by analysis |
| `validation_report.json`, `manifest.json` | `build_context_package` | durable forecast record (readiness/identity) | **yes** — required-member gate (A3) |
| `README.md`, `SCHEMA.md` | `write_text` | `export` | — |
| self-copy of generator `.py` | `shutil.copy2` | `evidence` | — |

### A5. Analysis generator (Phase 7) — `analysis/generate_forecast_analysis_package.py`

Reader side: `resolve_inputs` → `run_lineage.resolve_upstream("context")` then reads context
`canonical/*.jsonl`, `summaries/*`, `mapping/*`, `audit/reconciliation_report.json`,
`validation_report.json`, `manifest.json` — all **`runtime-input`** (consuming the A4 dual-role
artifacts). Writer side emits `forecast_analysis_package_<project>_<stamp>/`:

| Output member | Role | Dual-role |
| --- | --- | --- |
| `forecast_recommendations_by_budget_code.jsonl` | durable forecast record | **yes** — read by downstream (A9); required member (A3) |
| `forecast_risk_register.jsonl` | durable + `evidence` | possibly |
| `evidence_alignment_by_budget_code.jsonl`, `manual_mapping_review_items.jsonl`, `data_quality_warnings.jsonl` | `evidence` | — |
| `summaries/project_forecast_analysis.json` | durable forecast record | — |
| `summaries/top_forecast_movements.json`, `top_review_items.json` | `export` | — |
| `audit/*.json` (reconciliation, source_files_used, source_validation_snapshot, safety_scan) | `evidence` | — |
| `validation_report.json`, `manifest.json`, `input_inventory.json` | durable record / `evidence` | identity/lineage |
| `README.md`, `SCHEMA.md`, self-copy `.py` | `export` / `evidence` | — |

Related: `analysis/final_forecast_runner.py` (controlled runner wrapping run-analysis);
`analysis/generate_forecast_analysis_crosswalk_v2.py` (crosswalk variant, similar structure).

### A6. Mapping workpaper / crosswalk v2 (`mapping/`)

Emits `mapping_discrepancy_workpaper_<project>_<stamp>/`:
`owner_sov_to_budget_code_crosswalk.jsonl`, `procore_commitment_to_budget_code_crosswalk.jsonl`
(durable forecast records; **dual-role** if consumed downstream), plus discrepancy/
reconciliation/review JSONL (`evidence`) and `manifest.json`/`validation_report.json`.

### A7. Config registry (Phase 16) — `config_registry.py` + `workflows/forecast_db_config_backed_core.py`

| Symbol | Reads / writes | Role | Target DB |
| --- | --- | --- | --- |
| `config_registry.py:discover_config_sources` | `config/projects/<project>.json` → control file, model_controls, staffing mapping, owner_sov_crosswalk | `runtime-input` | V60 `forecast_config_*` |
| `config_registry.py:_config_base` | normalizes config root | `runtime-input` validation | — |
| `workflows/forecast_db_config_backed_core.py` (`_comprehensive_reads`/`_generic_reads`) | materializes a DB config snapshot to `work_root/materialized_config/`, bridges via `CFR_CONFIG_ROOT` | `runtime-input` materialization | V60 |

Note: config is read from **files**; the DB-config path *materializes a snapshot back to files*
and points `CFR_CONFIG_ROOT` at it (a bridge, not a direct DB read at generation time).

### A8. Workflows (`workflows/`, 15 modules) — roles

Mostly proof/readiness/certification scaffolding around the file/DB equivalence program.
Each reads packages/DB to *validate*, not to feed a production forecast.

| Module | Role |
| --- | --- |
| `controlled_db_context_analysis.py` | `evidence` (parity proof, no live write) |
| `db_certified_final_output.py` | `evidence` (certification) |
| `db_cutover_readiness.py` | `evidence` (readiness gate) |
| `forecast_comprehensive_db_config_proof.py` | `evidence` (config parity) |
| `forecast_db_config_backed_core.py` | `runtime-input` materialization (A7) |
| `forecast_db_config_backed_generation.py` | `runtime-input` entry (runs a generator with DB config) |
| `forecast_model_controls_db_config_proof.py` | `evidence` |
| `forecast_monthly_db_config_proof.py` | `evidence` |
| `forecast_probability_db_config_proof.py` | `evidence` |
| `guarded_db_operator_run.py` | `evidence` (gated handoff; no default flip) |
| `live_db_certification.py` | `evidence` (read-only live cert) |
| `live_db_config_registry_promotion.py` | `evidence`/promotion (config snapshot → active) |
| `live_db_source_domain_projection.py` | `evidence`/projection (live DB → test DB) |
| `temp_db_readiness_rehearsal.py` | `evidence` (temp-DB rehearsal) |

(14 workflow modules + `__init__.py` = 15 files, verified.)

### A9. Downstream domain generators (`forecast_*`, 15 packages) + `mapping/`

The 15 `forecast_*` packages (verified): `forecast_accuracy`, `forecast_actuals`,
`forecast_comprehensive`, `forecast_controls`, `forecast_cost_basis`, `forecast_cost_frequency`,
`forecast_dormancy`, `forecast_history_informed`, `forecast_improvement_audit`,
`forecast_intelligence`, `forecast_model_controls`, `forecast_monthly`, `forecast_probability`,
`forecast_staffing_basis`, `forecast_staffing_plan`.

Each consumes upstream package outputs (analysis `forecast_recommendations_by_budget_code.jsonl`
and context `canonical/*.jsonl`) as **`runtime-input`**, discovered via its **own** latest-glob
`package_discovery.py` / `*_io.py` (mechanism #2 above), **not** via `run_lineage.resolve_upstream`.
Each emits its own `forecast_<kind>_package_<project>_<stamp>/` directory (durable records +
evidence + export, same shape as A4/A5). This per-domain self-discovery is itself a dual-role /
shadow-DB dependency to migrate.

---

## Surface B — hb_assistant consumer / read-model (secondary)

Path: `src/hb_assistant/construction/forecast/` + `…/analytics/api.py`

| File:symbol | Reads | Role | Notes |
| --- | --- | --- | --- |
| `forecast/package_reader.py` | forecast package manifests from CFR run state | `runtime-input` (read-model) | feeds API |
| `forecast/run_reader.py` | `.cfr_run_state` + package manifests | `runtime-input` (read-model) | |
| `forecast/repository.py` | V58 foundation tables | DB read | lineage query builder |
| `forecast/source_domain_repository.py` | V59 source-domain tables | DB read | the `_READERS` target (A2) |
| `forecast/source_domain_engine.py` | V59 projection + `is_live_db_path` guard | DB read/projection | temp-DB only |
| `forecast/projection_engine.py` | Phase 2 lineage projection → V58 | DB write (temp only) | |
| `analytics/api.py` `/api/forecast/*` | serves package summaries/validation/rows/monthly/probability/risks from **package files** (via readers above), config/runs from DB foundation | mixed | read-model API; most package detail still file-sourced |

---

## File-handoff chain (where output becomes the next stage's runtime input)

```
External inputs (RUNTIME INPUT, file or DB via A2 toggle)
  twn_cost_forecast_json_package/*.jsonl   → V59 (toggle)
  owner_pay_app_json_package/*.jsonl       → no DB table (gap)
  cost_forecast_agent_db_json_export_*     → no DB table (gap)
        │
        ▼  (Phase 6 context generator)
  forecast_context_package_<p>_<stamp>/      ◀── DUAL-ROLE
     canonical/*.jsonl, summaries/*, mapping/owner_cost_code_family_crosswalk.jsonl,
     validation_report.json, manifest.json
        │  discovered via .cfr_run_state + run_lineage.resolve_upstream("context")  ◀── DUAL-ROLE (run-state file)
        ▼  (Phase 7 analysis generator)
  forecast_analysis_package_<p>_<stamp>/     ◀── DUAL-ROLE
     forecast_recommendations_by_budget_code.jsonl, validation_report.json, manifest.json
        │  discovered via run_lineage.resolve_upstream("analysis")
        ▼  (Phase 9+ downstream forecast_* generators)
  forecast_<kind>_package_<p>_<stamp>/  (durable + evidence + export)
        │
        ▼  (Surface B) hb_assistant read-model API serves package files (+ V58/V60 DB foundation)
```

## Dual-role artifact summary (highest-priority removal targets)

| Artifact | Written by | Read as runtime input by | DB home today |
| --- | --- | --- | --- |
| `.cfr_run_state/full_fresh_<p>_<run_id>.json` | run start / `record_latest` | every downstream stage (`resolve_upstream`) | **none** (file-only lineage) |
| `forecast_context_package/.../canonical/*.jsonl` | context generator (A4) | analysis (A5) + downstream (A9) | partial — 3 source-domain reads map to V59; emitted canonical set is broader |
| `forecast_context_package/.../summaries/*`, `validation_report.json`, `manifest.json` | context generator | analysis + package resolution gate | **none** |
| `forecast_analysis_package/.../forecast_recommendations_by_budget_code.jsonl` | analysis generator (A5) | downstream `forecast_*` (A9) | **none** — no `forecast_output_*` table exists |
| `forecast_analysis_package/.../validation_report.json`, `manifest.json` | analysis generator | package resolution gate | **none** |
| `forecast_<kind>_package/.../*.jsonl` (15 downstream packages) | each `forecast_*` generator | itself / sibling generators, via per-domain `package_discovery.py`/`*_io.py` latest-glob | **none** |
| config files (`config/projects/*.json`, controls, crosswalks) | (source/registry) | every generator (via `CFR_CONFIG_ROOT`) | V60 exists but bridge re-materializes to files |

See `runtime-dependency-removal-backlog.md` for prioritized migration targets and gaps.
