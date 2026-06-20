# ADR 276 — Forecast Phase 20: comprehensive DB-backed config consumer proof

- **Status:** Accepted
- **Date:** 2026-06-20
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 20
- **Builds on:** ADR 258–275 (Phases 2–19); Phase 16 (v60 config registry + `CFR_CONFIG_ROOT` bridge);
  Phase 18a (live-DB stability hardening); Phase 19 (`forecast_probability` consumer proof, PR #50 merge `f337db13`).

## Context

Phases 17/18/19 proved `forecast_model_controls`, `forecast_monthly`, and `forecast_probability` as DB-config
consumers. Phase 20 is the final consumer layer: **`forecast_comprehensive`**, the integrated forecast package
generator downstream of monthly/probability and upstream of the cutover decision. Proving it leaves nothing
between the registry and an integrated cutover.

### Repo-truth audit

- **Entrypoint:** `generate_comprehensive_forecast_package.generate(project_key, cfg, data_root, frozen_stamp,
  out_root, with_llm=False, llm_model=None, control_file=None)`. No `runs`/`seed` — the probability layer is a
  **deterministic transform** (`accepted_distribution_deterministic_adjustment`), not a fresh Monte Carlo.
  Byte-deterministic under a fixed `frozen_stamp` (`_determinism_check`; no `datetime.now` in the quantitative
  path; advisory LLM excluded). `with_llm` default **False**.
- **Reads predecessors read-only; runs no monthly/probability/intelligence generator** (grep-confirmed). DB
  opened `mode=ro` for inventory; no mutation outside the output package.
- **Direct config consumed through the `resolve_config_base` bridge — three domains:** `project`
  (`config/projects/tropical.json`, via the proof's `load_project`), `forecast_controls`
  (`fctl_integration.prepare`), `forecast_model_controls` (`fmc_integration.prepare`). Staffing / owner-SOV
  crosswalk are **not** re-resolved — comprehensive inherits those decisions from predecessor packages. **No
  reader-layer gap:** the module-level `SUBPROJECT_ROOT` is passed *into* `resolve_config_base` (already
  `CFR_CONFIG_ROOT`-aware), so — unlike Phase 19 — **no reader-layer fix was needed**.
- **Required predecessors (fail closed):** `context`, `intelligence` (`forecast_accuracy_next_package_*`),
  `monthly`. **Optional:** probability, history_informed, cost_frequency, crosswalk_v2, schedule_integrated,
  staffing_plan.
- **Embedded absolute paths** (`input_inventory.json`, `audit/source_packages_used.json`, the evidence
  registry) are **data_root package paths** — identical across both runs. A **mandatory raw file-backed vs
  DB-backed diff** confirmed the path-embedding set is **EMPTY** (`_PATH_EMBEDDING_FILES = ()`): every output
  file is byte-identical across the two runs.

## Decisions

### 1. cost_frequency guard (against the conditional upstream-generation branch)

`_maybe_generate_cost_frequency()` will GENERATE a `forecast_cost_frequency` package **into `data_root`** if one
is absent AND `cfg.forecast_comprehensive.frequency_enabled` (default True). That is an upstream generation + a
write into the read-only data root. The proof **refuses before any generation**: when `frequency_enabled`
resolves true, a `forecast_cost_frequency_package_tropical_*` is treated as a **proof-required predecessor**;
if absent → **rc 3** `required_predecessor_package_missing: forecast_cost_frequency`. The proof never sets
`frequency_enabled=false`, never mutates cfg, and never lets the generator run. Tests prove: refusal when
missing; pass when present; the cost-frequency generator monkeypatched to raise is **never called**; and the
`data_root` file inventory/bytes are **unchanged** before/after. Safety: `forecast_cost_frequency_run:false`,
`forecast_cost_frequency_package_read:true`, `predecessor_packages_generated:[]`, `source_package_mutated:false`.
If the real live data root lacks a cost-frequency package, the live proof **stops** (producing it is a separate
approved operator action, not part of Phase 20).

### 2. Package CSVs are standard deterministic output

`forecast_comprehensive`'s normal package contains `actuals_monthly_*.csv` and `actuals_plus_forecast_monthly_*.csv`
(historical actuals blended with the integrated forecast). These are **standard package outputs**, included in the
file-backed vs DB-backed comparison and **compared byte-exact** — never excluded or normalized.
`safety.integrated_csv_generated:false` means **"no SEPARATE final-integrated-CSV cutover/export deliverable was
produced outside the normal package."** It does **not** mean comprehensive is forbidden from writing its own
package CSVs. The report adds `standard_comprehensive_package_csvs_generated:true` and lists the CSV paths. Tests
prove the CSVs exist in both packages, are byte-exact, and that a CSV byte difference fails parity.

### New workflow — `workflows/forecast_comprehensive_db_config_proof.py`

`run_forecast_comprehensive_db_config_proof(*, project_key="tropical", live_db_path, config_snapshot_id,
work_root, run_stamp=None, data_root=None, source_config_root=None, require_live_snapshot=True,
require_item_count=194, preflight_stability_seconds=2.0)`. Self-contained adaptation of the Phase 19 workflow.

- **Gates (rc 3):** tropical; live DB pinned `mode=ro`, schema ≥ v60, 4 config tables; (when required) live DB;
  snapshot exists/matches project/item-count (194; `-1` skips); source config root; work-root isolation (not at/
  under the live forecast root, source config tree, live DB directory, or data root); the **three required**
  predecessors present; the **cost_frequency guard**.
- **Live-DB stability (inherited Phase 18a):** pinned `mode=ro` connection; quiescence preflight sampling
  `_live_db_state` (physical main/`-wal`/`-shm` + logical schema/`PRAGMA data_version`/db_inventory counts) twice,
  drift → rc 3 `live_db_not_quiescent`; measured before/after `live_db_integrity`; before/after drift →
  not_ready (rc 1) `live_db_mutated_during_run`.
- **Evidence-backed consumed accounting** from `mat["row_counts"]` for the three bridge-read files
  (`config/projects/<project>.json` + the controls + model-controls files);
  `consumed_config_domains=["forecast_controls","forecast_model_controls","project"]`; counts computed.
- **Two runs**, same `run_stamp`/`data_root`: file-backed (`CFR_CONFIG_ROOT` unset) and DB-backed
  (`CFR_CONFIG_ROOT`=materialized, scoped); each run's resolved controls/model-controls paths are recorded, and
  `db_snapshot_backed.reads_materialized_config` asserts the DB-backed run resolves those files **under the
  materialized root** (proving it reads the snapshot, not the repo). Byte-exact comparison; mandatory raw-diff →
  `_PATH_EMBEDDING_FILES = ()`. Factual `predecessor_packages.{required,optional,read,generated:[]}` and
  `standard_comprehensive_package_csvs` reported from the actual run.

### Additive CLI — `forecast-comprehensive-db-config-proof`

Required `--project/--live-db-path/--config-snapshot-id/--work-root`; optional `--run-stamp/--data-root/
--source-config-root/--expect-item-count[194;-1]/--no-require-live-snapshot/--preflight-stability-seconds[2.0]`.
No `--allow-live-db-write`. rc 0/1/3. `cli.py` additive only (only new Phase 20 lines actionable).

## Validation

Deterministic CI: reduced self-consistent config root (project + disabled controls/model + staffing/crosswalk so
snapshot=5 > consumed=3) imported to a temp v60 DB; a data_root with the required context+intelligence+monthly
packages **and a cost-frequency package**; `cli.SUBPROJECT_ROOT` + the comprehensive generator's `SUBPROJECT_ROOT`
monkeypatched; `db_inventory.resolve_db_path` neutralized; frozen stamp. Tests prove parity ready; evidence-backed
consumed accounting; empty raw-diff path-embedding set; **the DB-backed run resolves the materialized control
files** (report evidence + a monkeypatch recording the generator's resolution of the materialized model-control
file); the cost_frequency guard (refuse/pass/never-generate/data_root-unchanged); package CSVs present + byte-exact
+ a CSV diff fails parity; factual optional-predecessor reporting (probability absent → false); `audit/db_inventory.json`
not normalized; gate refusals; CLI rc 0/1/3; and the full Phase 18a stability suite. No schema/lifecycle/`hb_assistant`
change; file-backed default preserved; live DB read-only only.

## Deferred operator evidence run

The real proof against the live DB + snapshot `c3b4a67d22db47c74e696ae562fbf1c555e365fc66bb003a7b3312754415b698`
(`--expect-item-count 194 --preflight-stability-seconds 30`) is deferred until merge + live-writer quiescence. If
the live data root lacks a cost-frequency package, the live proof stops. Not run during implementation.

## Deferred (unchanged by Phase 20)

DB-backed config as a production default; the integrated cutover decision and any SEPARATE final-integrated-CSV
deliverable; the CLI-only secondary hardcoded reads; the −$3.42M reconciliation; Phase 21.
