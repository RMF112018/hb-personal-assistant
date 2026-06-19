# ADR 273 — Forecast Phase 17: model-controls DB-backed config consumer proof

- **Status:** Accepted
- **Date:** 2026-06-19
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 17
- **Builds on:** ADR 258–272 (Phases 2–16); Phase 16 (v60 config registry + `CFR_CONFIG_ROOT` bridge, PR #45 merge `96fdef5980041b0f99b848d7ea7b2c3d65afcf6c`).

## Context

Phase 16 built the v60 config registry, the `CFR_CONFIG_ROOT` opt-in bridge, and proved DB-backed config at
the **reader layer** + `validate-crosswalk`, but no *forecast generator* had yet been shown to consume a DB
config snapshot. Phase 17 closes that gap for the **smallest real config-consuming generator** —
`forecast_model_controls` — proving it produces **deterministic, parity-equivalent output** from (1) the
current file-backed config and (2) the materialized live Phase 16 DB config snapshot. It is a **consumer
proof only**: it changes no default, never writes/migrates the live DB, and does not widen into
monthly/comprehensive/probability/integrated-CSV or the Phase 6/7/9/12/15 chain.

### Why `forecast_model_controls`
Repo-truth audit confirmed it is the smallest generator that (a) **directly** consumes operator config —
exactly one file, `config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl`, via
`forecast_model_controls.load_controls.control_file_path` → `common.config_root.resolve_config_base`
(already `CFR_CONFIG_ROOT`-aware post-Phase-16) — and (b) runs **deterministically and standalone**:
`with_llm`/`llm_model` are dead params (zero LLM/Ollama/network), output is byte-stable under a frozen
stamp (the generator self-checks determinism), and it mutates nothing outside its output package. Its only
required input is **one context package** under the data root (`canonical/budget_codes.jsonl` +
`summaries/budget_code_forecast_context.jsonl`); intelligence/monthly/probability/comprehensive packages
are optional and degrade gracefully — so the proof needs **no out-of-scope workflow**.

### Honest consumption accounting
The full live snapshot holds **194** items across all config domains, but `forecast_model_controls` consumes
only the **5** model-control records. The report records both: `snapshot_item_count: 194`,
`consumed_snapshot_item_count: 5`, `consumed_config_domains: ["forecast_model_controls"]`,
`db_snapshot_consumed_files: [".../code_forecast_model_controls.jsonl"]`. The caller-supplied project `cfg`
is **not** read through the bridge and is **not** reported as a DB-snapshot-consumed input.

## Decision

### New CFR-only workflow `workflows/forecast_model_controls_db_config_proof.py`
`run_forecast_model_controls_db_config_proof(*, project_key="tropical", live_db_path, config_snapshot_id,
work_root, run_stamp=None, require_live_snapshot=True, data_root=None, source_config_root=None,
require_item_count=None)`. `ForecastModelControlsDbConfigProofError` (fail closed → rc 3). Reuses Phase 16
`config_registry.materialize_forecast_config_snapshot` and `common.config_root.ENV_CONFIG_ROOT`, and the
Phase 13 read-only connection helper.

**Gates (fail closed before output):** tropical project; explicit work root not under the live forecast
root and not the source config root; live DB exists and opened **READ-ONLY** (`mode=ro`); schema ≥ v60; the
4 config registry tables present; (when `require_live_snapshot`) the path resolves to the live/default DB;
the snapshot row exists with `project_key='tropical'`; (when `require_item_count`, CLI default 194) the
snapshot item count matches; source config root + data root + context package exist.

**Execution:** materialize the snapshot under `<work_root>/db_snapshot_config/materialized_config` (read-only
on the DB; never writes repo `config/`); load `cfg` once with `CFR_CONFIG_ROOT` unset; run the real generator
**file-backed** (`CFR_CONFIG_ROOT` unset → repo default, output under `file_backed/`) and **DB-backed**
(`CFR_CONFIG_ROOT` = materialized root, set inside a **try/finally** and restored, output under
`db_snapshot_backed/`), both with the same frozen `run_stamp`.

### `CFR_CONFIG_ROOT` scope
Used exactly per Phase 16 semantics (the override base contains a `config/` subtree). The file-backed run
proves the **default is preserved** (env unset); the DB-backed run sets the env only around the single
generator call and restores the prior value in `finally` (`cfr_config_root_restored: true`). It is never a
production default and never set globally.

### Parity comparison (minimal, explicit normalization)
- **Tier 1 — 17 semantic files** (the model-control forecast/audit data, which embed no path): compared
  **byte-exact, no normalization**. Any difference is a real mismatch.
- **Tier 2 — path-embedding files** (`project_forecast_model_controls_summary.json`, `input_inventory.json`,
  `audit/source_hashes_before_after.json`, `audit/safety_scan_report.json`, `README.md`, `SCHEMA.md`):
  compared **path-normalized** (output-package roots → `<OUTPUT_PACKAGE>`, repo/materialized config roots →
  `<CONFIG_ROOT>`); their non-path content is still compared.
- **Tier 3 — `manifest.json` / `validation_report.json`** (record per-file sha256/size): the **sha256 and
  size_bytes of the Tier-2 files only** are excluded/neutralized (they differ solely because those files
  record an absolute config/output path); the 17 semantic files' sha256/size are NOT excluded.

No semantic, control, forecast, row-count, warning, validation-status, or semantic-file hash is normalized.
On mismatch the workflow returns `not_ready` (rc 1) and reports, per differing file: `file`, `key_or_path`,
`file_backed_value`, `db_backed_value`, and the `normalized_rules` applied.

### Additive CLI
`forecast-model-controls-db-config-proof` (`--project --live-db-path --config-snapshot-id --work-root`;
`--run-stamp`, `--data-root`, `--source-config-root`, `--expect-item-count` [default 194; `-1` to skip],
`--no-require-live-snapshot` [dev/test]). **No `--allow-live-db-write`** — this workflow never writes the
live DB. rc 0 parity ready / 1 mismatch / 3 refusal. All existing commands unchanged.

## Scope boundary

Phase 17 proves ONLY `forecast_model_controls`. It does **not** prove monthly, comprehensive, probability,
integrated CSV, or the Phase 6/7/9/12/15 controlled chain — those remain deferred. The real live proof
(against the live DB + the Phase 16 live snapshot `c3b4a67d…`) is a separate operator action after
review/merge; implementation/tests used temp DBs + a minimal synthetic context package and never touched the
real live DB.

## Consequences

- First demonstration that an actual config-consuming forecast generator runs identically (modulo recorded
  config-file path) from a governed DB config snapshot vs the file-backed default — the consumer half of the
  Phase 16 bridge.
- No schema change (stays v60); no lifecycle change; no `hb_assistant` change; file-backed config remains the
  default and fully tested; live DB read-only only.

## Deferred (unchanged by Phase 17)

- DB-backed config as a production default; broader consumers (monthly/comprehensive/probability/staffing).
- Integrated CSV; model-backed/LLM/Ollama/intelligence; the Phase 6/7/9/12/15 chain consuming config.
- v58 `forecast_package_manifests` resolver; `forecast_project_config_values`; the −$3.42M reconciliation;
  Phase 18.
