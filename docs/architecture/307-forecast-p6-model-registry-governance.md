# 307 — Forecast P6: model-registry / versioning / weighting / calibration governance (Gap 6)

- Status: accepted
- Date: 2026-06-24
- Phase: forecast-model remediation P6
- Gap: #6 (model registry / selection / weighting governance)

## Context

The forecast estimators, backtest calibration weights, and reconciliation reliability weights are
hardcoded CFR constants computed at runtime and never persisted: `forecast_accuracy/estimators.py`
(`INDEPENDENT_METHODS`/`ERP_METHODS` + thresholds), `backtest.py` (inverse-MAPE calibration centred
on 1.0, written only into the accuracy-package JSON), `reconcile.py` (`RELIABILITY_WEIGHT`). There is
no record of **which** methodology / weights / thresholds produced a given run, and the two V66
governance tables `forecast_method_eligibility` / `forecast_model_selection_decisions` ship empty
because the default run path never threads an `accuracy_package` into decision-support.

## Decision

Add a DB-backed model registry and persist per-run model-version + calibration provenance, gated by
a default-off flag, writing only to a NON-LIVE temp DB.

1. **Schema — migration v72** (`store/forecast_model_registry_tables.py`, additive
   `CREATE TABLE IF NOT EXISTS`, all `operational_empty_expected`):
   - `forecast_model_versions` — one immutable row per methodology, deduped by `methodology_sha256`
     (estimator order, reliability weights, thresholds, backtest cohort).
   - `forecast_run_model_versions` — per-run linkage `run_id -> forecast_runs.run_id`, plus the
     accuracy-package stamp as a **separate** provenance field.
   - `forecast_calibration_weights` — per-run, per-method calibration provenance. `calibration_source`
     distinguishes the four `BACKTEST_METHODS` (`backtest`) from the independent method the cohort omits
     (`not_backtested`, `schedule_etc`) and the ERP baselines (`reliability_only`). `mape`/`mean_bias`/
     `calibration_weight` are NULL unless `backtest`.
   - Lifecycle contract `table_count` 433 -> 436; all 19 hardcoded assertions bumped in lockstep.

2. **CFR methodology descriptor** — `generate_forecast_accuracy_package.py` emits a new
   `model_methodology.json` (estimator order, reliability weights, thresholds, cohort params, and a
   `methodology_sha256` over those constants). It is **deterministic and path-free** (no timestamps,
   no filesystem paths), so it is byte-stable across runs (the e2e determinism test stays green) and
   hb_assistant can version the methodology without duplicating CFR constants (no drift). CFR imports
   no hb_assistant.

3. **Persistence + flag** — `construction/forecast/model_registry_repository.py` reads the descriptor
   + `audit/calibration_snapshot.json` and upserts the three tables (idempotent, dedup-by-sha). It is
   wired into `project_decision_support` behind `HB_FORECAST_MODEL_GOVERNANCE_ENABLED` (default OFF):
   on-flag + apply it persists provenance in the same transaction after `apply_plan`; **fail-closed**
   before any write if `run_id` / `accuracy_package` / `model_methodology.json` is missing. Flag-off is
   byte-identical (no model-registry rows, no `model_provenance` in the result). The existing
   `_emit_method_rollups` already populates `forecast_method_eligibility` / `forecast_model_selection_decisions`
   whenever an `accuracy_package` is threaded — unchanged by this PR.

## Scope refinement (vs. the original plan)

The plan proposed recording the per-run model version in the `forecast_db_config_run_service` JSON run
record. Tracing the code showed that service records a **config-snapshot** generation run — a distinct
concept from the decision-support **projection** run that consumes the accuracy package; the two do not
share a record. The architecturally correct home for "per-run model version recorded" is therefore the
`forecast_run_model_versions` table (keyed by the projection `run_id`), which this PR creates. This
avoids touching the run-service DTO/redaction surface entirely. The JSON-record addition is dropped.

The accuracy-package generator remains tropical-coupled (package name, manifest, `through_may_2026`
bucket); decoupling it is a P4c/P4d concern and is **not** addressed here. hb_assistant stays decoupled
via the explicit `accuracy_package` path (the established P2/P2b/P3 explicit-path + flag pattern).

## Validation

- New `tests/test_migrator_v72_forecast_model_registry.py` (additive migration, idempotency, FKs,
  `calibration_source`, lifecycle classification) and `tests/test_forecast_model_registry_p6.py`
  (flag-on provenance + `calibration_source` mapping, flag-off byte-identical, idempotent dedup,
  fail-closed without methodology, pure row-builder). Both added to `scripts/test-forecasting.sh`.
- CFR `test_forecast_accuracy_e2e.py` (incl. byte determinism) stays green with the new file.
- `scripts/test-forecasting.sh` + `scripts/test-schedule.sh` (migrator touched -> cross-domain canary).
- No live-DB write; copied/temp-DB evidence only. No `raw_json`/path in any user-facing API.
