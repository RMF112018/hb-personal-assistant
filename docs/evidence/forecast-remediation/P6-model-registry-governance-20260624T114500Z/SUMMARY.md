# P6 — Model registry / versioning / weighting / calibration governance (Gap 6)

Evidence bundle for forecast-remediation **P6**. ADR 307.

## What shipped

1. **Migration v72** (`store/forecast_model_registry_tables.py`) — 3 additive
   `operational_empty_expected` tables: `forecast_model_versions` (immutable, deduped by
   `methodology_sha256`), `forecast_run_model_versions` (per-run linkage to
   `forecast_runs.run_id`; accuracy-package stamp = separate provenance), and
   `forecast_calibration_weights` (per-run, per-method; `calibration_source` =
   `backtest` / `not_backtested` / `reliability_only`). `LATEST_SCHEMA_VERSION` 71→72.
   Lifecycle contract `table_count` 433→436; **all 19** hardcoded assertions bumped in lockstep.
2. **CFR methodology descriptor** — `generate_forecast_accuracy_package.py` emits a
   deterministic, path-free `model_methodology.json` (methodology constants + `methodology_sha256`).
   CFR imports no hb_assistant; e2e byte-determinism stays green.
3. **Governance persistence** — `construction/forecast/model_registry_repository.py` reads the
   descriptor + `audit/calibration_snapshot.json` and persists the 3 tables (idempotent,
   dedup-by-sha). Wired into `project_decision_support` behind default-off
   `HB_FORECAST_MODEL_GOVERNANCE_ENABLED`; fail-closed before any write if
   `run_id`/`accuracy_package`/`model_methodology.json` is missing; flag-off byte-identical.

## Scope decisions

- Per-run model version recorded in the `forecast_run_model_versions` table (the projection-run
  home), NOT the `forecast_db_config_run_service` JSON record (a distinct config-snapshot run).
- Accuracy-package tropical-coupling left to P4c/P4d; hb_assistant decoupled via the explicit
  `accuracy_package` path (P2/P2b/P3 pattern).

## Validation

- `scripts/test-forecasting.sh` → **0 failing, 876 passed** (863 on main + 13 new:
  7 `test_migrator_v72_forecast_model_registry.py` + 6 `test_forecast_model_registry_p6.py`).
- `scripts/test-schedule.sh` → **0 failing**; migrator/schema tests green (v72 + 433→436 bump
  safe cross-domain).
- CFR `test_forecast_accuracy_e2e.py` → 4 passed incl. byte determinism with the new file.
- No live-DB write; temp/copied-DB only. New tests added to the forecasting bundle allowlist.

## Plan-gate / sensitive-op

- `hb-implementation-plan-reviewer`: APPROVE WITH CHANGES — all 5 required changes incorporated
  (19-assert enumeration, deterministic path-free descriptor, `calibration_source` column,
  run_id-FK identity, bundle allowlist).
- `hb-sensitive-operation-gate`: Proceed with constraints (additive, temp-DB only, live DB
  untouched, idempotent, redaction) — all honored.
