"""V63 forecast run-output table names and DDL statements.

The model-run OUTPUT family: where a forecast run's own results live in the DB
(distinct from V61's external-forecast-evaluation tables, which evaluate
operator-supplied forecasts). ``forecast_outputs`` is the per-run header; the
``forecast_output_*`` children hold the detail. Every row keeps the original
package row verbatim in ``raw_json`` (authoritative shape for read-parity);
money values are stored as TEXT (Decimal strings), never floats.

Additive ``CREATE TABLE IF NOT EXISTS`` only; ships empty
(``operational_empty_expected``) and is populated only by the read-only
output projector into a temp DB — never the live DB.
"""

from __future__ import annotations

V63_TABLES: tuple[str, ...] = (
    "forecast_outputs",
    "forecast_output_budget_codes",
    "forecast_output_monthly",
    "forecast_output_probability",
    "forecast_output_risks",
    "forecast_output_changes",
    "forecast_output_commitment_exposure",
    "forecast_output_staffing",
    "forecast_output_schedule_phasing",
    "forecast_output_narratives",
)

V63_STATEMENTS: list[str] = [
    # --- run-output header -------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_outputs (
      output_id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      source_package TEXT NOT NULL,
      forecast_period TEXT,
      basis_labels TEXT,
      estimated_final_cost TEXT,
      forecast_at_completion TEXT,
      cost_to_complete TEXT,
      variance_to_budget TEXT,
      variance_to_prior_forecast TEXT,
      source_path TEXT,
      source_sha256 TEXT,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      FOREIGN KEY (run_id) REFERENCES forecast_runs(run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_outputs_project ON forecast_outputs(project_key);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_outputs_run ON forecast_outputs(run_id);",
    # --- per-budget-code recommendations -----------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_budget_codes (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      budget_code_key TEXT,
      cost_code TEXT,
      category TEXT,
      forecast_action TEXT,
      recommended_projected_cost TEXT,
      recommended_cost_to_complete TEXT,
      confidence TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, budget_code_key),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_budget_codes_output ON forecast_output_budget_codes(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_budget_codes_project ON forecast_output_budget_codes(project_key);",
    # --- monthly forecast curve (deferred population) ----------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_monthly (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      budget_code_key TEXT,
      month TEXT,
      value TEXT,
      is_actual INTEGER NOT NULL DEFAULT 0,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, budget_code_key, month),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_output ON forecast_output_monthly(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_project ON forecast_output_monthly(project_key);",
    # --- probability bands (deferred population) ----------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_probability (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      scope TEXT,
      budget_code_key TEXT,
      p10 TEXT,
      p50 TEXT,
      p90 TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, scope, budget_code_key),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_probability_output ON forecast_output_probability(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_probability_project ON forecast_output_probability(project_key);",
    # --- risk register ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_risks (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      risk_id TEXT,
      severity TEXT,
      budget_code_key TEXT,
      cost_code TEXT,
      category TEXT,
      risk_type TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, risk_id),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_risks_output ON forecast_output_risks(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_risks_project ON forecast_output_risks(project_key);",
    # --- output deltas vs prior run (deferred population) -------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_changes (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      budget_code_key TEXT,
      change_type TEXT,
      delta_amount TEXT,
      prior_run_id TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, budget_code_key, change_type),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_changes_output ON forecast_output_changes(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_changes_project ON forecast_output_changes(project_key);",
    # --- commitment exposure (deferred population) --------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_commitment_exposure (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      budget_code_key TEXT,
      committed_amount TEXT,
      exposure_amount TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, budget_code_key),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_commitment_exposure_output ON forecast_output_commitment_exposure(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_commitment_exposure_project ON forecast_output_commitment_exposure(project_key);",
    # --- staffing (deferred population) -------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_staffing (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      budget_code_key TEXT,
      role TEXT,
      month TEXT,
      headcount TEXT,
      cost_amount TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, budget_code_key, role, month),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_staffing_output ON forecast_output_staffing(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_staffing_project ON forecast_output_staffing(project_key);",
    # --- schedule phasing (deferred population) -----------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_schedule_phasing (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      budget_code_key TEXT,
      phase TEXT,
      start_month TEXT,
      end_month TEXT,
      amount TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, budget_code_key, phase),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_schedule_phasing_output ON forecast_output_schedule_phasing(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_schedule_phasing_project ON forecast_output_schedule_phasing(project_key);",
    # --- narratives ---------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_narratives (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      scope TEXT,
      narrative_key TEXT,
      source_row_number INTEGER,
      raw_json TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, scope, narrative_key),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_narratives_output ON forecast_output_narratives(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_narratives_project ON forecast_output_narratives(project_key);",
]
