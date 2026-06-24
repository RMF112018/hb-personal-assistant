"""V72 forecast model-registry table names and DDL statements.

Model governance (forecast-remediation P6, Gap 6). The forecast_accuracy estimators, the
backtest calibration weights, and the reconciliation reliability weights are otherwise
hardcoded CFR constants computed at runtime and never persisted — there is no record of
*which* methodology / weights / thresholds produced a given forecast run. This schema gives
that provenance a queryable DB home keyed to a forecast run:

- forecast_model_versions          : one immutable row per distinct methodology (deduped by
                                     methodology_sha256) — estimator order, reliability weights,
                                     thresholds, backtest-cohort params.
- forecast_run_model_versions      : per-run linkage to the methodology version in effect
                                     (run_id -> forecast_runs.run_id), plus the separate
                                     accuracy-package stamp as provenance.
- forecast_calibration_weights     : per-run, per-method calibration provenance from the
                                     backtest. calibration_source distinguishes the methods the
                                     backtest actually weighted from those it does not (the CFR
                                     BACKTEST_METHODS set is a strict subset of the 7 estimators).

All values are TEXT (Decimal strings / JSON), never floats. Additive CREATE TABLE IF NOT
EXISTS only; ships empty (operational_empty_expected) and is populated only by the read-only
decision-support / governance path into a temp DB, never the live DB.
"""

from __future__ import annotations

V72_TABLES: tuple[str, ...] = (
    "forecast_model_versions",
    "forecast_run_model_versions",
    "forecast_calibration_weights",
)

V72_STATEMENTS: list[str] = [
    # --- model versions: one immutable row per distinct methodology (dedup by sha) ------
    """
    CREATE TABLE IF NOT EXISTS forecast_model_versions (
      model_version_id TEXT PRIMARY KEY,
      version_label TEXT NOT NULL,
      methodology_sha256 TEXT NOT NULL,
      estimator_order_json TEXT NOT NULL,
      reliability_weights_json TEXT NOT NULL,
      thresholds_json TEXT,
      cohort_json TEXT,
      source TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(methodology_sha256)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_model_versions_label ON forecast_model_versions(version_label);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_model_versions_sha ON forecast_model_versions(methodology_sha256);",
    # --- per-run model-version linkage (run_id -> forecast_runs.run_id) -----------------
    """
    CREATE TABLE IF NOT EXISTS forecast_run_model_versions (
      run_id TEXT PRIMARY KEY,
      model_version_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      version_label TEXT,
      methodology_sha256 TEXT NOT NULL,
      accuracy_package_stamp TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id),
      FOREIGN KEY (model_version_id) REFERENCES forecast_model_versions(model_version_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_run_model_versions_model ON forecast_run_model_versions(model_version_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_run_model_versions_project ON forecast_run_model_versions(project_key);",
    # --- per-run, per-method calibration provenance ------------------------------------
    # calibration_source: 'backtest' (MAPE-weighted), 'not_backtested' (independent method the
    # backtest cohort omits, e.g. schedule_etc), or 'reliability_only' (ERP baselines, which
    # carry no calibration multiplier). mape/mean_bias/calibration_weight are NULL unless
    # calibration_source = 'backtest'.
    """
    CREATE TABLE IF NOT EXISTS forecast_calibration_weights (
      id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      method TEXT NOT NULL,
      calibration_source TEXT NOT NULL,
      mape TEXT,
      mean_bias TEXT,
      calibration_weight TEXT,
      reliability_weight TEXT,
      reason TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(run_id, method),
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_calibration_weights_run ON forecast_calibration_weights(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_calibration_weights_project ON forecast_calibration_weights(project_key);",
]
