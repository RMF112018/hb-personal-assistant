# ADR 275 — Forecast Phase 19: probability DB-backed config consumer proof

- **Status:** Accepted
- **Date:** 2026-06-20
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 19
- **Builds on:** ADR 258–274 (Phases 2–18a); Phase 16 (v60 config registry + `CFR_CONFIG_ROOT` bridge);
  Phase 18 (`forecast_monthly` consumer proof) + Phase 18a (live-DB stability hardening, PR #49 merge `9e5b35ce`).

## Context

Phase 17 proved `forecast_model_controls`, Phase 18 proved `forecast_monthly`, and Phase 18a hardened that
proof to fail closed on live-DB volatility (the first live proof failed because Procore live-sync wrote the
app DB mid-run). Phase 19 extends the proof to **`forecast_probability`** — the Monte-Carlo validation package
downstream of monthly and **upstream of `forecast_comprehensive`** (the final integrated generator). Proving
probability now leaves comprehensive as the only remaining consumer before an integrated cutover.

A concrete repo-truth gap blocked it: `forecast_probability/simulation_inputs.py::_owner_scope_by_key()`
resolved the owner-SOV crosswalk under a hardcoded `Path(__file__).resolve().parents[3]` instead of the
`CFR_CONFIG_ROOT`-aware `resolve_config_base()`, so it would ignore a materialized snapshot.

### Repo-truth audit

- **Byte-deterministic** under fixed `(seed, runs, frozen_stamp, inputs)`: a single `np.random.default_rng(seed)`;
  the internal `_determinism_check` confirms a byte-identical quantitative core; advisory LLM is off and
  excluded. So a file-backed vs DB-backed parity proof is viable.
- **Required predecessors (both, else SystemExit):** `forecast_accuracy_next_package_tropical_*` and
  `forecast_monthly_package_tropical_*`. It **reads** the monthly package (incl.
  `audit/forecast_model_controls_applied.json` for accepted operator caps) read-only and **never regenerates
  monthly**, runs no comprehensive, generates no integrated CSV, and imports no `fctl/fmc/fsp` integrations.
- **Consumed config via the bridge — exactly two domains:** `project` (`config/projects/tropical.json`, via the
  workflow's `cli.load_project`) and `owner_sov_crosswalk` (the exact `cfg["owner_sov_scope_crosswalk"]` JSONL
  at `config/crosswalks/tropical/...`, via `_owner_scope_by_key` after the fix). The sibling crosswalk `.csv`
  materializes but is **not read**, so it is not counted as consumed. Counts are computed from the materialized
  snapshot metadata (`mat["row_counts"]`), never constants.
- Writes `audit/db_inventory.json` (opens the live DB `mode=ro`) — the same live-DB volatility surface Phase 18a
  hardened. `audit/source_files_used.json` embeds only data_root/local_db paths that are identical across both
  runs.

## Decision

### Narrow config-bridge fix — `forecast_probability/simulation_inputs.py`

Added a module-level `SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]` and
`from ..common.config_root import resolve_config_base`, and changed `_owner_scope_by_key`'s path resolution to
`path = Path(rel) if Path(rel).is_absolute() else (resolve_config_base(SUBPROJECT_ROOT) / rel)` (mirror idiom:
`forecast_controls/load_controls.py::control_file_path`). **Default behavior is byte-identical when
`CFR_CONFIG_ROOT` is unset** (`resolve_config_base` returns `SUBPROJECT_ROOT`); the constant makes the root
monkeypatchable for the deterministic test. This is the only reader-layer change. A **secondary** hardcoded read
exists in `generate_probabilistic_validation_package.py::main()` (project cfg under `SUBPROJECT_ROOT`) — it is
CLI-`main()`-only, not on the reader path the proof uses, and is deferred (not changed).

### New workflow — `workflows/forecast_probability_db_config_proof.py`

A self-contained adaptation of the Phase 18a monthly proof (reuses `cert`/`config_registry`/`sha256_file`;
duplicates the stability + comparison helpers per the phase-module convention so Phase 18a stays untouched).
`run_forecast_probability_db_config_proof(... runs=10000, seed=20260614, forecast_start_month=None,
preflight_stability_seconds=2.0 ...)`:

- **Gates (rc 3):** tropical; live DB pinned `mode=ro`, schema ≥ v60, 4 config tables; (when required) the live
  DB; snapshot exists/matches project/item-count (194; `-1` skips); source config root; **work-root isolation**
  — not at/under the live forecast root, source config tree, live DB directory, **or the data root / source
  packages**; data_root (read-only input, may be the live forecast root) holds **both** predecessors.
- **Live-DB stability (inherited from Phase 18a):** one pinned `mode=ro` connection across the whole proof (so
  the reused materialize cannot induce a checkpoint); a quiescence preflight sampling `_live_db_state` (physical
  main/`-wal`/`-shm` `size/mtime_ns/sha256` + logical `schema_version`/`PRAGMA data_version`/db_inventory
  counts+digest) twice, drift → rc 3 `live_db_not_quiescent`; measured before/after `live_db_integrity`;
  before/after drift → `not_ready` (rc 1) `live_db_mutated_during_run`.
- **Evidence-backed consumed accounting:** only the files probability actually reads through the bridge
  (`config/projects/<project>.json` + the exact crosswalk JSONL), counts from `mat["row_counts"]`; the `.csv` is
  excluded. `consumed_config_domains=["owner_sov_crosswalk","project"]`.
- **Two runs**, same `run_stamp`/`runs`/`seed`/`forecast_start_month`/`data_root`: file-backed (`CFR_CONFIG_ROOT`
  unset) and DB-backed (`CFR_CONFIG_ROOT`=materialized, scoped). LLM off; monthly/comprehensive/CSV never run.
- **Comparison:** byte-exact for every file. A **mandatory raw file-backed vs DB-backed diff** confirmed the
  path-embedding set is **EMPTY** (`_PATH_EMBEDDING_FILES = ()`); the report records `comparison.path_embedding_files`
  + `raw_diff_inspected: true`. `manifest.json`/`validation_report.json` neutralize size/sha only for enumerated
  path-embedding files (none). **No** probability/monthly value, row count, warning, validation status, manifest
  conclusion, `audit/db_inventory.json` content, or math output is ever normalized.
- **Report** (`report_schema_version:1`): status/decision/`not_ready_reason`, snapshot vs consumed accounting,
  `probability_run:{runs,seed,forecast_start_month}`, comparison, `live_db_integrity`, and the measured `safety`
  block (`forecast_probability_run:true`, `forecast_monthly_run:false`, `forecast_monthly_package_read:true`,
  `forecast_accuracy_next_package_read:true`, comprehensive/CSV/LLM/intelligence all false).

### Additive CLI — `forecast-probability-db-config-proof`

Required `--project/--live-db-path/--config-snapshot-id/--work-root`; optional `--run-stamp/--data-root/
--source-config-root/--expect-item-count[194;-1]/--no-require-live-snapshot/--preflight-stability-seconds[2.0]/
--runs[10000]/--seed[20260614]/--forecast-start-month`. No `--allow-live-db-write`. rc 0/1/3. `cli.py` additive
only (only new Phase 19 lines are actionable; not mass-formatted).

## Validation

Deterministic CI: a reduced self-consistent config root (project + crosswalk + controls/model/staffing so
snapshot=5 > consumed=2) imported to a temp v60 DB; a minimal data_root with both predecessor packages; small
`runs` + fixed `seed` + frozen stamp; `cli.SUBPROJECT_ROOT` and `simulation_inputs.SUBPROJECT_ROOT` monkeypatched
at the reduced root; `db_inventory.resolve_db_path` neutralized. Tests prove: parity ready; evidence-backed
consumed accounting (project + owner_sov_crosswalk; csv excluded); empty path-embedding set raw-diff-confirmed;
the `_owner_scope_by_key` bridge reads the materialized crosswalk under `CFR_CONFIG_ROOT` (and a tamper →
`config_parity_mismatch`); **probability never calls the monthly generator** (monkeypatched to raise);
`CFR_CONFIG_ROOT` restored; gate refusals; CLI rc 0/1/3; the full Phase 18a stability suite (preflight pass/refusal,
WAL/SHM + `data_version` fingerprints, during-run drift → not_ready, pin prevents proof-induced change, no live
write). `audit/db_inventory.json` is kept byte-exact (a real parity signal). No schema/lifecycle/`hb_assistant`
change; file-backed default preserved; live DB read-only only.

## Deferred operator evidence run

The real proof against the live DB + snapshot `c3b4a67d22db47c74e696ae562fbf1c555e365fc66bb003a7b3312754415b698`
(`--expect-item-count 194`, `--runs 10000 --seed 20260614 --preflight-stability-seconds 30`) is deferred until
this PR is merged AND the live writer (HB morning automation / Procore live-sync) is quiesced — the preflight
otherwise refuses rc 3. Evidence ZIP excludes `__MACOSX`/`._*`/`.DS_Store`. Not run during implementation.

## Deferred (unchanged by Phase 19)

`forecast_comprehensive` consumer proof + integrated CSV; DB-backed config as a production default; the CLI-only
secondary hardcoded read in `generate_probabilistic_validation_package.py::main()`; the v58
`forecast_package_manifests` resolver; the −$3.42M reconciliation; Phase 20.
