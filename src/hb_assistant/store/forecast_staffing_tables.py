"""V76 Project Staffing foundation: table names and DDL statements.

Project Staffing turns the per-project Staffing tab into a forecast-impacting configuration
surface. This V76 slice is **schema + seed only** (Phase 1): it adds the staffing table family
and seeds the default company holiday calendar. No repositories, services, API routes, UI, or
forecast-generation wiring live here — those land in later phases.

Tables added (additive ``CREATE TABLE IF NOT EXISTS``; money stored as TEXT Decimal strings,
dates as ISO ``YYYY-MM-DD`` / ``YYYY-MM`` TEXT, JSON payloads as TEXT):

- ``staffing_holiday_calendars`` / ``staffing_holiday_calendar_dates`` — company holiday
  calendar family; seeded with ``company_default_2026_2040`` (2026-2040) by the migration.
- ``forecast_project_staffing_assumptions`` — per-project hours/holiday-calendar assumptions.
- ``forecast_project_staffing_config`` — the staffing assignment rows (role/person/cost-code/
  LAB-LBN-MAT rates/dates) + validation + template-override metadata.
- ``forecast_project_staffing_absence_overrides`` — Full-Time absence reductions.
- ``forecast_staffing_templates`` / ``forecast_staffing_template_versions`` — global reusable
  staffing templates with version history.
- ``forecast_staffing_cost_codes`` — forecast-only staffing cost codes (project- or
  template-scoped) for codes absent from the project budget.
- ``forecast_project_staffing_attribution_rules`` — persistent LAB/LBN actual-to-row
  attribution rules.
- ``forecast_project_staffing_attribution_review_items`` — aggregated unmatched LAB/LBN actual
  review bucket (employee + cost_code + category).
- ``forecast_cost_entry_staffing_actuals`` — normalized staffing-actuals projection over
  ``forecast_cost_entries.raw_json`` (LAB/LBN attributable; MAT summarized, not person-matched).
- ``forecast_project_staffing_snapshots`` / ``forecast_project_staffing_snapshot_rows`` — the
  exact resolved staffing configuration captured per forecast run so historical outputs stay
  reproducible after later config/template edits.

Additive column metadata on the existing v74 matrix-row table lets the monthly matrix
distinguish budget-code rows from staffing LAB/LBN person rows and staffing MAT summary rows;
columns ship unpopulated (the DB-native generation path populates them in a later phase).
"""

from __future__ import annotations

V76_TABLES: tuple[str, ...] = (
    "staffing_holiday_calendars",
    "staffing_holiday_calendar_dates",
    "forecast_project_staffing_assumptions",
    "forecast_project_staffing_config",
    "forecast_project_staffing_absence_overrides",
    "forecast_staffing_templates",
    "forecast_staffing_template_versions",
    "forecast_staffing_cost_codes",
    "forecast_project_staffing_attribution_rules",
    "forecast_project_staffing_attribution_review_items",
    "forecast_cost_entry_staffing_actuals",
    "forecast_project_staffing_snapshots",
    "forecast_project_staffing_snapshot_rows",
)

# Additive matrix-row staffing metadata (SOW 3.11). Applied only when absent so re-apply under
# the schedule self-heal path is idempotent (raw ALTER lists would error on re-run). Unpopulated
# at introduction; the DB-native generation/persistence path fills them in a later phase.
V76_MATRIX_ROW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("row_type", "TEXT DEFAULT 'budget_code'"),
    ("staffing_config_id", "TEXT"),
    ("role_title", "TEXT"),
    ("person_name", "TEXT"),
    ("employee_name_normalized", "TEXT"),
    ("source_budget_code_key", "TEXT"),
    ("attribution_status", "TEXT"),
)
V76_COLUMN_ADDITIONS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("forecast_output_monthly_table_rows", V76_MATRIX_ROW_COLUMNS),
)

V76_CREATE_STATEMENTS: list[str] = [
    # --- holiday calendar family (seeded by the migration) ------------------------------
    """
    CREATE TABLE IF NOT EXISTS staffing_holiday_calendars (
      holiday_calendar_id TEXT PRIMARY KEY,
      calendar_key TEXT NOT NULL UNIQUE,
      calendar_name TEXT NOT NULL,
      description TEXT,
      active_status TEXT NOT NULL DEFAULT 'active',
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS staffing_holiday_calendar_dates (
      holiday_date_id TEXT PRIMARY KEY,
      holiday_calendar_id TEXT NOT NULL,
      calendar_year INTEGER NOT NULL,
      holiday_key TEXT NOT NULL,
      holiday_name TEXT NOT NULL,
      holiday_date TEXT NOT NULL,
      observed_date TEXT NOT NULL,
      duration_type TEXT NOT NULL DEFAULT 'full_day',
      closed_from_time TEXT,
      closed_until_time TEXT,
      staffing_hours_excluded TEXT NOT NULL DEFAULT '8.00',
      notes TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      UNIQUE(holiday_calendar_id, calendar_year, holiday_key),
      FOREIGN KEY (holiday_calendar_id) REFERENCES staffing_holiday_calendars(holiday_calendar_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_staffing_holiday_calendar_dates_calendar_year "
    "ON staffing_holiday_calendar_dates(holiday_calendar_id, calendar_year);",
    # --- global staffing templates ------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_staffing_templates (
      template_id TEXT PRIMARY KEY,
      template_key TEXT NOT NULL UNIQUE,
      template_name TEXT NOT NULL,
      active_status TEXT NOT NULL DEFAULT 'active',
      current_version_id TEXT,
      created_by_role TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      deactivated_utc TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS forecast_staffing_template_versions (
      template_version_id TEXT PRIMARY KEY,
      template_id TEXT NOT NULL,
      version_number INTEGER NOT NULL,
      cost_code TEXT NOT NULL,
      cost_code_description TEXT,
      default_role_title TEXT,
      default_employment_type TEXT,
      default_rate_unit TEXT,
      default_lab_rate TEXT,
      default_lbn_rate TEXT,
      default_mat_rate TEXT,
      created_by_role TEXT,
      created_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}',
      UNIQUE(template_id, version_number),
      FOREIGN KEY (template_id) REFERENCES forecast_staffing_templates(template_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_staffing_template_versions_template "
    "ON forecast_staffing_template_versions(template_id);",
    # --- per-project assumptions --------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_assumptions (
      project_key TEXT PRIMARY KEY,
      hours_per_business_day TEXT NOT NULL DEFAULT '8.00',
      business_days_per_week TEXT NOT NULL DEFAULT '5.00',
      full_time_hours_per_week TEXT NOT NULL DEFAULT '40.00',
      holiday_calendar_id TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY (holiday_calendar_id) REFERENCES staffing_holiday_calendars(holiday_calendar_id)
    );
    """,
    # --- project staffing config rows ---------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_config (
      staffing_config_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      template_id TEXT,
      role_title TEXT NOT NULL,
      person_name TEXT,
      person_name_normalized TEXT,
      employment_type TEXT NOT NULL,
      cost_code TEXT NOT NULL,
      cost_code_description TEXT,
      rate_unit TEXT NOT NULL,
      lab_rate TEXT,
      lbn_rate TEXT,
      mat_rate TEXT,
      start_date TEXT NOT NULL,
      finish_date TEXT NOT NULL,
      active_status TEXT NOT NULL DEFAULT 'active',
      override_fields_json TEXT NOT NULL DEFAULT '[]',
      validation_status TEXT NOT NULL DEFAULT 'valid',
      validation_errors_json TEXT NOT NULL DEFAULT '[]',
      created_by_role TEXT,
      updated_by_role TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      deactivated_utc TEXT,
      raw_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_config_project "
    "ON forecast_project_staffing_config(project_key, active_status);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_config_cost_code "
    "ON forecast_project_staffing_config(project_key, cost_code);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_config_person "
    "ON forecast_project_staffing_config(project_key, person_name_normalized);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_config_template "
    "ON forecast_project_staffing_config(template_id);",
    # --- absence overrides (Full-Time only) ---------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_absence_overrides (
      absence_override_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      staffing_config_id TEXT,
      person_name TEXT,
      person_name_normalized TEXT,
      start_date TEXT NOT NULL,
      finish_date TEXT NOT NULL,
      absence_hours TEXT NOT NULL,
      notes TEXT,
      active_status TEXT NOT NULL DEFAULT 'active',
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      deactivated_utc TEXT,
      raw_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY (staffing_config_id)
        REFERENCES forecast_project_staffing_config(staffing_config_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_absence_project "
    "ON forecast_project_staffing_absence_overrides(project_key, active_status);",
    # --- forecast-only staffing cost codes ----------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_staffing_cost_codes (
      staffing_cost_code_id TEXT PRIMARY KEY,
      project_key TEXT,
      template_id TEXT,
      cost_code TEXT NOT NULL,
      cost_code_description TEXT,
      source_scope TEXT NOT NULL DEFAULT 'project_staffing',
      active_status TEXT NOT NULL DEFAULT 'active',
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_staffing_cost_codes_project "
    "ON forecast_staffing_cost_codes(project_key, cost_code);",
    # --- LAB/LBN actual attribution rules -----------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_attribution_rules (
      attribution_rule_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      employee_name_source TEXT NOT NULL,
      employee_name_normalized TEXT NOT NULL,
      cost_code TEXT NOT NULL,
      category TEXT NOT NULL,
      staffing_config_id TEXT NOT NULL,
      match_source TEXT NOT NULL,
      confidence TEXT,
      effective_start_date TEXT,
      effective_finish_date TEXT,
      active_status TEXT NOT NULL DEFAULT 'active',
      created_by_role TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY (staffing_config_id)
        REFERENCES forecast_project_staffing_config(staffing_config_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_attribution_rules_lookup "
    "ON forecast_project_staffing_attribution_rules"
    "(project_key, cost_code, category, employee_name_normalized);",
    # --- LAB/LBN unmatched-actual review bucket (aggregated, not per-transaction) --------
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_attribution_review_items (
      review_item_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      employee_name_source TEXT NOT NULL,
      employee_name_normalized TEXT NOT NULL,
      cost_code TEXT NOT NULL,
      category TEXT NOT NULL,
      actuals_start_month TEXT,
      actuals_through_month TEXT,
      actual_amount TEXT,
      suggested_staffing_config_id TEXT,
      suggested_confidence TEXT,
      review_status TEXT NOT NULL DEFAULT 'unmatched',
      resolved_staffing_config_id TEXT,
      resolved_by_role TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_review_items_project "
    "ON forecast_project_staffing_attribution_review_items(project_key, review_status);",
    # --- normalized staffing-actuals projection over forecast_cost_entries.raw_json -----
    """
    CREATE TABLE IF NOT EXISTS forecast_cost_entry_staffing_actuals (
      staffing_actual_id TEXT PRIMARY KEY,
      cost_entry_id TEXT,
      project_key TEXT NOT NULL,
      budget_code_key TEXT,
      cost_code TEXT,
      category TEXT,
      accounting_date TEXT,
      accounting_month TEXT,
      amount TEXT,
      description TEXT,
      employee_name_source TEXT,
      employee_name_normalized TEXT,
      is_employee_attributable INTEGER NOT NULL DEFAULT 0,
      attribution_status TEXT NOT NULL DEFAULT 'unmatched',
      staffing_config_id TEXT,
      attribution_rule_id TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_cost_entry_staffing_actuals_project "
    "ON forecast_cost_entry_staffing_actuals(project_key, cost_code, category);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_cost_entry_staffing_actuals_person "
    "ON forecast_cost_entry_staffing_actuals(project_key, employee_name_normalized);",
    # --- per-run staffing snapshot (reproducibility) ------------------------------------
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_snapshots (
      staffing_snapshot_id TEXT PRIMARY KEY,
      request_id TEXT,
      output_id TEXT,
      project_key TEXT NOT NULL,
      source_hash TEXT,
      template_versions_json TEXT NOT NULL DEFAULT '[]',
      project_assumptions_json TEXT NOT NULL DEFAULT '{}',
      holiday_calendar_id TEXT,
      validation_status TEXT NOT NULL DEFAULT 'valid',
      validation_errors_json TEXT NOT NULL DEFAULT '[]',
      created_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_snapshots_project "
    "ON forecast_project_staffing_snapshots(project_key);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_snapshots_output "
    "ON forecast_project_staffing_snapshots(output_id);",
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_snapshot_rows (
      snapshot_row_id TEXT PRIMARY KEY,
      staffing_snapshot_id TEXT NOT NULL,
      staffing_config_id TEXT,
      template_id TEXT,
      template_version_id TEXT,
      project_key TEXT NOT NULL,
      row_identity_key TEXT,
      role_title TEXT,
      person_name TEXT,
      person_name_normalized TEXT,
      employment_type TEXT,
      cost_code TEXT,
      category TEXT,
      rate_unit TEXT,
      rate TEXT,
      start_date TEXT,
      finish_date TEXT,
      created_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY (staffing_snapshot_id)
        REFERENCES forecast_project_staffing_snapshots(staffing_snapshot_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_snapshot_rows_snapshot "
    "ON forecast_project_staffing_snapshot_rows(staffing_snapshot_id);",
]


# ---------------------------------------------------------------------------------------------
# V81 attribution reshape (cost_code + category model).
#
# The V76 attribution_rules / review_items tables were person-centric (employee_name_* NOT NULL),
# but real forecast_cost_entries carry no per-person identity in `description`, so attribution
# keys on cost_code + category with manual operator rules. Both tables ship EMPTY, so the V81
# migration drops + recreates them (abort-if-nonempty guarded, one-time). Count-neutral.
V81_RESHAPE_TABLES: tuple[str, ...] = (
    "forecast_project_staffing_attribution_rules",
    "forecast_project_staffing_attribution_review_items",
)
V81_DROP_STATEMENTS: list[str] = [
    "DROP TABLE IF EXISTS forecast_project_staffing_attribution_rules;",
    "DROP TABLE IF EXISTS forecast_project_staffing_attribution_review_items;",
]
V81_CREATE_STATEMENTS: list[str] = [
    # Manual LAB/LBN attribution rules: (project_key, cost_code, category) -> staffing_config_id.
    # Active-uniqueness on (project_key, cost_code, category) is enforced at the service layer
    # (the repo has no partial-unique-index precedent); a regular lookup index backs it.
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_attribution_rules (
      attribution_rule_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      cost_code TEXT NOT NULL,
      category TEXT NOT NULL,
      staffing_config_id TEXT NOT NULL,
      match_source TEXT NOT NULL DEFAULT 'manual',
      effective_start_date TEXT,
      effective_finish_date TEXT,
      active_status TEXT NOT NULL DEFAULT 'active',
      created_by_role TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY (staffing_config_id)
        REFERENCES forecast_project_staffing_config(staffing_config_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_attribution_rules_lookup "
    "ON forecast_project_staffing_attribution_rules(project_key, cost_code, category);",
    # Aggregated unmatched LAB/LBN actual review bucket, keyed by project_key + cost_code + category
    # (NOT person). description_label is context only.
    """
    CREATE TABLE IF NOT EXISTS forecast_project_staffing_attribution_review_items (
      review_item_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      cost_code TEXT NOT NULL,
      category TEXT NOT NULL,
      description_label TEXT,
      actuals_start_month TEXT,
      actuals_through_month TEXT,
      actual_amount TEXT,
      suggested_staffing_config_id TEXT,
      review_status TEXT NOT NULL DEFAULT 'unmatched',
      resolved_staffing_config_id TEXT,
      resolved_by_role TEXT,
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      raw_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_project_staffing_review_items_project "
    "ON forecast_project_staffing_attribution_review_items(project_key, review_status);",
]
