# ADR 274 — Forecast Phase 18: monthly DB-backed config consumer proof

- **Status:** Accepted
- **Date:** 2026-06-19
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 18
- **Builds on:** ADR 258–273 (Phases 2–17); Phase 16 (v60 config registry + `CFR_CONFIG_ROOT` bridge, PR #45 merge `96fdef5980041b0f99b848d7ea7b2c3d65afcf6c`); Phase 17 (`forecast_model_controls` consumer proof, PR #47 merge `ea1b441be7fb9736e00e8d0b0c28c0ecabc46f78`).

## Context

Phase 16 migrated the operator-approved forecast config into the v60 SQLite registry and added the opt-in
`CFR_CONFIG_ROOT` bridge that lets a materialized snapshot stand in for the file-backed `config/` tree.
Phase 17 proved the **smallest** real config consumer (`forecast_model_controls`) produces output that is
parity-equivalent whether it reads file-backed config or a materialized DB snapshot. Phase 18 extends that
proof to the next, larger consumer — **`forecast_monthly`** — the month-by-month generator that time-phases
the accepted forecast-intelligence final-cost package.

This is a **consumer proof only**: it changes no default, never writes/migrates/imports the live DB, runs no
LLM/Ollama, and does not run `forecast_comprehensive` / `forecast_probability` or generate any integrated CSV.

### Repo-truth audit — why `forecast_monthly` is safe to isolate

- **No out-of-scope imports.** `forecast_monthly/generate_monthly_forecast_package.py` imports neither
  `forecast_comprehensive` nor `forecast_probability`, and emits no integrated CSV. Advisory LLM/Ollama is
  engaged only via the opt-in `--with-llm` flag (default off, explicitly excluded from the determinism gate);
  the proof runs it off.
- **Deterministic under a frozen stamp.** `generate(..., frozen_stamp=...)` fixes the package name and
  `generated_timestamp_local`; the in-process `_determinism_check` confirms the quantitative core is
  byte-identical. `forecast_as_of_date` is the system date but is identical across the two in-process runs.
- **Read-only.** The generator mutates nothing outside its output package. It opens the configured local
  inventory DB strictly read-only (`db_inventory` → `mode=ro`) — a **read**, never a write.
- **Required inputs.** Monthly fails closed (SystemExit) without three predecessor packages in the data root:
  `forecast_context_package_tropical_*`, `forecast_analysis_package_tropical_crosswalk_v2_*`, and the accepted
  `forecast_accuracy_next_package_tropical_*`. The accepted accuracy package is an **input read**, not an
  intelligence-workflow run.

### Config consumed through the bridge (exact accounting)

`forecast_monthly` reads **four** config domains through `common/config_root.py::resolve_config_base`
(already `CFR_CONFIG_ROOT`-aware):

| Domain | Read via | Materialized relative path |
|---|---|---|
| `project` | `cli.load_project()` | `config/projects/tropical.json` |
| `forecast_controls` | `fctl_integration.prepare` → `load_controls.control_file_path` | `config/forecast_controls/tropical/code_forecast_controls.jsonl` |
| `forecast_model_controls` | `fmc_integration.prepare` → `load_controls.control_file_path` | `config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl` |
| `forecast_staffing` | `fsp_integration.prepare` → `load_mapping.mapping_file_path` | `config/forecast_staffing/tropical/staffing_budget_code_mapping.jsonl` |

The owner-SOV crosswalk and the staffing **source package** come from the data root / project config, not the
materialized config paths, so they are **not** counted as DB-snapshot-consumed. The report records the full
snapshot item count separately from the consumed count and lists the exact consumed domains/files.

## Decision

### New CFR-only workflow `workflows/forecast_monthly_db_config_proof.py`

`run_forecast_monthly_db_config_proof(*, project_key="tropical", live_db_path, config_snapshot_id, work_root,
run_stamp=None, data_root=None, source_config_root=None, require_live_snapshot=True, require_item_count=194)`.
The suggested `upstream_*_package` parameters were **narrowed to `data_root` discovery**: monthly auto-discovers
its three required predecessor packages via its own `schedule_io.discover_packages` / latest-glob contract, so
explicit per-package overrides would diverge from repo truth.

**Gates (fail closed → `ForecastMonthlyDbConfigProofError` → CLI rc 3):** tropical project; live DB exists +
opened **read-only** (`mode=ro`) + schema ≥ v60 + the 4 config registry tables; (when `require_live_snapshot`)
the db_path is the live/default DB; snapshot row exists + matches the project; (when `require_item_count`) the
item count matches; source config root exists; **work-root artifact isolation** — `work_root` (and therefore
all generated artifacts) must not be at/under the live forecast root, the source config tree, or the live DB
directory; the data root holds the three required predecessor packages.

**Artifact isolation vs read-only input (corrected scope).** The forecast **data root MAY be the canonical/live
Tropical forecast data root** — it is a read-only input and is *not* rejected for that. Only the generated
artifacts — `work_root`, the two output packages, the materialized snapshot config, reports, summaries, and any
temp DBs — must live outside the live forecast root, source package, repo config tree, and live DB directory.

**Execution:** materialize the snapshot under `<work_root>/db_snapshot_config/materialized_config` (read-only on
the live DB). Run the real monthly generator twice with the same frozen stamp: **file-backed** (`CFR_CONFIG_ROOT`
unset → repo default; cfg reloaded from repo config; output under `file_backed/`) and **DB-backed**
(`CFR_CONFIG_ROOT` = materialized root, scoped in `try/finally`; cfg **reloaded under the env** so the `project`
domain is genuinely consumed too; output under `db_snapshot_backed/`). LLM is off; no comprehensive/probability/CSV.

### `CFR_CONFIG_ROOT` scope

Exactly Phase 16 semantics (the override base contains the `config/` subtree). The file-backed run asserts the
env is unset (default preservation). The DB-backed run sets the env only around the cfg-load + generator call and
restores the prior value in `finally`; it is never set globally and never becomes a production default. Unlike
Phase 17's single cfg load, Phase 18 **reloads the project config per run** because monthly reads `project.json`
through the bridge — reloading under the env genuinely consumes the `project` domain from the snapshot (the
snapshot project.json was imported from repo config in Phase 16, so cfg is identical → parity holds).

### Parity comparison (minimal, explicit normalization)

Every output file is compared **byte-exact** except an explicitly enumerated set that legitimately embeds an
absolute config-root/output-package path, which is compared after **path normalization only**:

- **Path-embedding files** (`audit/forecast_controls_applied.json`, `audit/forecast_model_controls_applied.json`,
  `audit/staffing_plan_applied.json`, `audit/safety_scan_report.json`): the file-backed/DB-backed output-package
  roots are replaced with `<OUTPUT_PACKAGE>` and the source/materialized config roots with `<CONFIG_ROOT>`; their
  non-path content is still compared exactly. (In the deterministic fixture only the two controls-applied audits
  actually differ; the list is the complete set of files that record a consumed-config/scanned-output path.)
- **`manifest.json` / `validation_report.json`:** the `size_bytes`/`sha256` of those path-embedding files are
  neutralized (they differ only because the underlying file records an absolute path); every other file is
  required byte-exact and its size/sha is **not** neutralized.
- **No** forecast/monthly value, row count, applied control, risk flag, warning, validation status, determinism
  hash, or any financial/math output is ever normalized.

Parity → `status=ready`, `decision=forecast_monthly_db_config_parity_ready`, `comparison.result=pass`,
`differences=[]` (rc 0); any mismatch → `not_ready` (rc 1) with the exact differing file/key/value.

### Safety block (reads distinguished from writes/runs)

`live_db_written/migrated/imported=false`, `source_config_mutated=false`, `source_package_mutated=false`,
`production_defaults_changed=false`, `cfr_config_root_default_changed=false`, `forecast_comprehensive_run=false`,
`forecast_probability_run=false`, `integrated_csv_generated=false`, `model_backed_llm_or_ollama_run=false`,
`intelligence_workflow_run=false`; and the affirmative reads/run: `live_db_snapshot_read=true`,
`monthly_db_inventory_read=true`, `forecast_accuracy_next_package_read=true`, `db_snapshot_config_consumed=true`,
`file_backed_default_preserved=true`, `forecast_monthly_run=true`.

### Additive CLI

`forecast-monthly-db-config-proof` (`--project`, `--live-db-path`, `--config-snapshot-id`, `--work-root`
required; `--run-stamp`, `--data-root`, `--source-config-root`, `--expect-item-count` [default 194; `-1` skips],
`--no-require-live-snapshot` optional). No `--allow-live-db-write` (the workflow never writes the live DB). rc 0
parity ready / 1 mismatch / 3 refusal. `cli.py` is additive only and not ruff-format-enforced.

## Live DB usage

The live config-snapshot DB is opened **read-only** (`mode=ro`) for the gate checks; the reused Phase 16
materializer runs read-only SELECTs to emit the snapshot tree. The configured local inventory DB is opened
`mode=ro` by `db_inventory` during the monthly run — a read, never a write. The real Phase 18 live proof (against
the live DB + the Phase 16 live snapshot `c3b4a67d22db47c74e696ae562fbf1c555e365fc66bb003a7b3312754415b698`, with
`--expect-item-count 194` and the live forecast data root) is a **separate operator action** after review/merge;
implementation and tests used a temp v60 DB + a self-consistent reduced config + a synthetic data root and never
touched the real live DB.

## Scope boundary

Proves **only** that `forecast_monthly` consumes DB-backed config with parity vs file-backed. It does not flip
defaults, does not make DB-backed config the default, does not run comprehensive/probability, generates no
integrated CSV, runs no model-backed/LLM/Ollama/intelligence workflow, and does not touch the Phase 6/7/9/12/15
chain. The deterministic CI fixture uses a reduced 5-item snapshot (4 consumed + 1 crosswalk) to prove the
mechanism; the real 194-item consumption is the deferred operator run.

## Consequences

- A second, larger config-consuming generator is proven to run identically from a governed DB snapshot vs the
  file-backed default, across all four config domains it reads.
- No schema change (stays v60); no lifecycle-count change; no `hb_assistant` change. File-backed monthly remains
  the default and fully tested. The live DB is read-only only.

## Deferred (unchanged by Phase 18)

DB-backed config as a production default; broader consumers (comprehensive/probability); integrated CSV;
model-backed/LLM/Ollama/intelligence; the v58 `forecast_package_manifests` resolver; `forecast_project_config_values`;
the −$3.42M reconciliation; Phase 19.
