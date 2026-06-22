"""V66 forecast decision-support table names and DDL statements.

The maturity-aware / resilient-to-incomplete-data layer: per-run, queryable persistence of
decision-support that is already *computed* elsewhere (CFR model_engines_readiness maturity
tiers + coverage, forecast_accuracy confidence bands/evidence-depth, the analysis package's
confidence_rollup.json) — this schema gives it a DB home keyed to a forecast run/output.

Every confidence score persists its factor-level explanation (forecast_confidence_factors):
no confidence without a recorded reason. Scores/money are TEXT (Decimal strings), never floats.

Additive CREATE TABLE IF NOT EXISTS only; ships empty (operational_empty_expected) and is
populated only by the read-only decision-support engine into a temp DB, never the live DB.
"""

from __future__ import annotations

V66_TABLES: tuple[str, ...] = (
    "forecast_project_maturity_snapshots",
    "forecast_data_availability_profiles",
    "forecast_method_eligibility",
    "forecast_model_selection_decisions",
    "forecast_confidence_scorecards",
    "forecast_confidence_factors",
    "forecast_operator_assumptions",
    "forecast_required_assumptions",
)

V66_STATEMENTS: list[str] = [
    # --- project maturity snapshot (M0-M5 per run) -------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_project_maturity_snapshots (
      snapshot_id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      source_package TEXT,
      maturity_tier TEXT,
      completed_month_count INTEGER,
      nonzero_month_count INTEGER,
      lifecycle_signal TEXT,
      basis TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(run_id, project_key, source_package),
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_maturity_snapshots_run ON forecast_project_maturity_snapshots(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_maturity_snapshots_project ON forecast_project_maturity_snapshots(project_key);",
    # --- per-domain data availability profile ------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_data_availability_profiles (
      id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      source_package TEXT,
      domain TEXT NOT NULL,
      availability TEXT,
      coverage TEXT,
      freshness TEXT,
      completeness TEXT,
      mapping_quality TEXT,
      maturity TEXT,
      score TEXT,
      reason TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(run_id, domain),
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_data_availability_profiles_run ON forecast_data_availability_profiles(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_data_availability_profiles_project ON forecast_data_availability_profiles(project_key);",
    # --- method eligibility (schema only this phase) -----------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_method_eligibility (
      id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      method TEXT NOT NULL,
      status TEXT,
      weight TEXT,
      reason TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(run_id, method),
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_method_eligibility_run ON forecast_method_eligibility(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_method_eligibility_project ON forecast_method_eligibility(project_key);",
    # --- model selection decisions (schema only this phase) ----------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_model_selection_decisions (
      id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      method TEXT NOT NULL,
      contributed INTEGER NOT NULL DEFAULT 0,
      weight TEXT,
      reason TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(run_id, method),
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_model_selection_decisions_run ON forecast_model_selection_decisions(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_model_selection_decisions_project ON forecast_model_selection_decisions(project_key);",
    # --- confidence scorecards (project / budget_code / method scope) ------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_confidence_scorecards (
      scorecard_id TEXT PRIMARY KEY,
      run_id TEXT,
      output_id TEXT,
      project_key TEXT NOT NULL,
      scope TEXT NOT NULL,
      scope_key TEXT,
      score TEXT,
      label TEXT,
      rollup_json TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(run_id, scope, scope_key),
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_confidence_scorecards_run ON forecast_confidence_scorecards(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_confidence_scorecards_project ON forecast_confidence_scorecards(project_key);",
    # --- confidence factors (the persisted explanation) --------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_confidence_factors (
      id TEXT PRIMARY KEY,
      scorecard_id TEXT NOT NULL,
      run_id TEXT,
      project_key TEXT NOT NULL,
      factor_key TEXT NOT NULL,
      direction TEXT,
      magnitude TEXT,
      reason TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(scorecard_id, factor_key),
      FOREIGN KEY (scorecard_id) REFERENCES forecast_confidence_scorecards(scorecard_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_confidence_factors_scorecard ON forecast_confidence_factors(scorecard_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_confidence_factors_run ON forecast_confidence_factors(run_id);",
    # --- operator assumptions (schema only; future operator UI) ------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_operator_assumptions (
      assumption_id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      assumption_type TEXT NOT NULL,
      budget_code_key TEXT,
      value TEXT,
      unit TEXT,
      source TEXT,
      operator TEXT,
      confidence_impact TEXT,
      is_required INTEGER NOT NULL DEFAULT 0,
      reused_from_prior INTEGER NOT NULL DEFAULT 0,
      overridden INTEGER NOT NULL DEFAULT 0,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_operator_assumptions_run ON forecast_operator_assumptions(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_operator_assumptions_project ON forecast_operator_assumptions(project_key);",
    # --- required assumptions (schema only) --------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_required_assumptions (
      id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      assumption_type TEXT NOT NULL,
      reason TEXT,
      satisfied INTEGER NOT NULL DEFAULT 0,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(run_id, assumption_type),
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_required_assumptions_run ON forecast_required_assumptions(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_required_assumptions_project ON forecast_required_assumptions(project_key);",
]
