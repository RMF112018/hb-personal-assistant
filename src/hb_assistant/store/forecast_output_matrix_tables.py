"""V74 forecast monthly-matrix table names and DDL statements.

Operator month-window matrix (Phase: monthly forecast matrix). Extends the v63 run-output family
so a forecast output is explainable strictly in terms of four operator-selected month windows and
exposes a table-ready, budget-code-by-month matrix:

- ``forecast_generation_requests`` / ``forecast_outputs`` gain the four ``YYYY-MM`` window fields
  (actuals start/through, forecast start/end). They are persisted on the immutable output so the
  matrix stays explainable even if the request row changes.
- ``forecast_output_monthly`` gains ``value_type`` / ``source_status`` so every monthly cell is
  classifiable without re-deriving from ``is_actual`` (retained for backward compatibility). Cells
  stay SPARSE — only real source actuals and emitted forecast cells are persisted; the dense
  254-row x N-month matrix is assembled (zero-filled) at read time by the monthly-table endpoint.
- ``forecast_output_monthly_table_rows`` holds persisted per-row matrix metadata (Completed-to-Date,
  Forecast-to-Complete, EAC, Variance) plus the display-vs-calculation projected-budget split:
  the Procore-authoritative ``projected_budget_display`` (what the matrix shows) and the
  financial-spine ``projected_budget_calculation_basis`` (engine continuity), with a warning field
  when they diverge or no Procore row maps.
- ``forecast_output_monthly_table_totals`` holds the dense per-month total row (every displayed
  month, certified) plus the scalar column totals — part of the certified output contract.

Money values are stored as TEXT (Decimal strings), never floats. The two new tables use additive
``CREATE TABLE IF NOT EXISTS``; the column additions use ``ALTER TABLE ADD COLUMN`` (run once, inside
the version guard) and existing rows remain valid (NULL window metadata => legacy output; NULL
``value_type`` is backfilled from ``is_actual`` for the pre-migration cells).
"""

from __future__ import annotations

V74_TABLES: tuple[str, ...] = (
    "forecast_output_monthly_table_rows",
    "forecast_output_monthly_table_totals",
)

# Column additions as (name, decl) tuples — the migrator adds each only when absent, so the set is
# idempotent and safe under the schedule routes' self-heal re-apply (which can leave the columns
# present while the v74 schema_migrations row is missing). Raw ALTER lists would error on re-run.
V74_REQUEST_COLUMNS: tuple[tuple[str, str], ...] = (
    ("actuals_start_month", "TEXT"),
    ("actuals_through_month", "TEXT"),
    ("forecast_start_month", "TEXT"),
    ("forecast_end_month", "TEXT"),
)
V74_OUTPUT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("actuals_start_month", "TEXT"),
    ("actuals_through_month", "TEXT"),
    ("forecast_start_month", "TEXT"),
    ("forecast_end_month", "TEXT"),
    ("month_window_basis", "TEXT"),
    ("month_window_warnings_json", "TEXT"),
)
# Unambiguous monthly cell classification (is_actual retained for backward compatibility).
V74_MONTHLY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("value_type", "TEXT"),
    ("source_status", "TEXT DEFAULT 'calculated'"),
)
V74_COLUMN_ADDITIONS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("forecast_generation_requests", V74_REQUEST_COLUMNS),
    ("forecast_outputs", V74_OUTPUT_COLUMNS),
    ("forecast_output_monthly", V74_MONTHLY_COLUMNS),
)
# Backfill the pre-migration v73 cells from is_actual so no row is left unclassified. Idempotent
# (the WHERE clause matches only not-yet-classified rows), so it is safe to run on every apply.
V74_BACKFILL_STATEMENTS: list[str] = [
    """
    UPDATE forecast_output_monthly
       SET value_type = CASE WHEN is_actual = 1 THEN 'actual' ELSE 'forecast' END,
           source_status = CASE WHEN is_actual = 1 THEN 'source_actual' ELSE 'calculated_forecast' END
     WHERE value_type IS NULL
    """,
]

V74_CREATE_STATEMENTS: list[str] = [
    # --- per-row matrix metadata --------------------------------------------------------
    # projected_budget split (revision 3): *_display is Procore-authoritative (what the matrix
    # shows + variance is computed against); *_calculation_basis is the financial-spine value kept
    # for engine continuity; *_source_warning is set warning-grade when they diverge or no Procore
    # row maps. variance_to_budget here = EAC - projected_budget_display (distinct from the header's
    # spine-based variance, which is not overwritten).
    """
    CREATE TABLE IF NOT EXISTS forecast_output_monthly_table_rows (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      budget_code_key TEXT NOT NULL,
      budget_code TEXT,
      cost_code TEXT,
      cost_type TEXT,
      projected_budget_display TEXT NOT NULL,
      projected_budget_display_source TEXT,
      projected_budget_calculation_basis TEXT NOT NULL,
      projected_budget_calculation_source TEXT,
      projected_budget_source_warning TEXT,
      completed_to_date TEXT NOT NULL,
      forecast_to_complete TEXT NOT NULL,
      estimated_at_completion TEXT NOT NULL,
      variance_to_budget TEXT NOT NULL,
      confidence TEXT,
      method_code TEXT,
      reason_codes_json TEXT,
      sort_key TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id, budget_code_key),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_table_rows_output "
    "ON forecast_output_monthly_table_rows(output_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_table_rows_output_cost_type "
    "ON forecast_output_monthly_table_rows(output_id, cost_type);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_table_rows_output_cost_code "
    "ON forecast_output_monthly_table_rows(output_id, cost_code);",
    # --- dense per-month total row ------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_output_monthly_table_totals (
      id TEXT PRIMARY KEY,
      output_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      month_values_json TEXT NOT NULL,
      projected_budget_total TEXT NOT NULL,
      completed_to_date_total TEXT NOT NULL,
      forecast_to_complete_total TEXT NOT NULL,
      estimated_at_completion_total TEXT NOT NULL,
      variance_to_budget_total TEXT NOT NULL,
      created_utc TEXT NOT NULL,
      updated_utc TEXT,
      UNIQUE(output_id),
      FOREIGN KEY (output_id) REFERENCES forecast_outputs(output_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_table_totals_output "
    "ON forecast_output_monthly_table_totals(output_id);",
    # --- composite indexes on the sparse monthly cell table (SOW 3.6) -------------------
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_output_code "
    "ON forecast_output_monthly(output_id, budget_code_key);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_output_month "
    "ON forecast_output_monthly(output_id, month);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_output_monthly_output_value_type "
    "ON forecast_output_monthly(output_id, value_type);",
]

