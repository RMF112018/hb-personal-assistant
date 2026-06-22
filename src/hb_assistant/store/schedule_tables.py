"""V62 schedule intelligence table names and DDL statements.

Canonical schedule activity storage for Procore API responses and uploaded
XML/XER/CSV files. SQLite is the source of truth after operator-confirmed import.
"""

from __future__ import annotations

V62_TABLES: tuple[str, ...] = (
    "schedule_file_imports",
    "procore_ep_schedule_activities",
    "procore_ep_schedule_relationships",
    "procore_ep_schedule_wbs_nodes",
    "procore_ep_schedule_calendars",
    "procore_ep_schedule_activity_code_assignments",
    "procore_ep_schedule_udf_values",
    "schedule_version_diffs",
    "schedule_quality_findings",
    "schedule_cost_mapping_runs",
    "schedule_cost_mapping_candidates",
    "schedule_cost_distributions",
    "schedule_cost_weighting_results",
)

V62_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_file_imports (
      import_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      procore_project_id TEXT,
      source_type TEXT NOT NULL CHECK(source_type IN ('procore_api', 'xml', 'xer', 'csv')),
      source_format TEXT NOT NULL CHECK(source_format IN (
        'procore_json', 'primavera_pmxml', 'primavera_xer', 'csv'
      )),
      source_filename_redacted TEXT,
      source_file_sha256 TEXT,
      source_payload_sha256 TEXT,
      parser_name TEXT,
      parser_version TEXT,
      import_status TEXT NOT NULL DEFAULT 'previewed' CHECK(import_status IN (
        'previewed', 'committed', 'failed', 'superseded'
      )),
      validation_status TEXT,
      activity_count INTEGER NOT NULL DEFAULT 0,
      relationship_count INTEGER NOT NULL DEFAULT 0,
      wbs_count INTEGER NOT NULL DEFAULT 0,
      calendar_count INTEGER NOT NULL DEFAULT 0,
      code_count INTEGER NOT NULL DEFAULT 0,
      udf_count INTEGER NOT NULL DEFAULT 0,
      cost_loaded_status TEXT NOT NULL DEFAULT 'not_cost_loaded' CHECK(cost_loaded_status IN (
        'not_cost_loaded', 'possible', 'verified', 'unreconciled'
      )),
      schedule_version_key TEXT,
      evidence_package_id TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      created_by_operator TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_file_imports_project ON schedule_file_imports(project_key);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_file_imports_status ON schedule_file_imports(import_status);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_file_imports_version ON schedule_file_imports(schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS procore_ep_schedule_activities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      procore_project_id TEXT,
      schedule_table_id TEXT,
      schedule_id TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      source_type TEXT NOT NULL,
      source_format TEXT NOT NULL,
      activity_id TEXT NOT NULL,
      source_activity_object_id TEXT,
      parent_activity_id TEXT,
      wbs_id TEXT,
      wbs_code TEXT,
      wbs_path TEXT,
      activity_name TEXT,
      activity_type TEXT,
      activity_status TEXT,
      planned_start TEXT,
      planned_finish TEXT,
      start_date TEXT,
      finish_date TEXT,
      early_start TEXT,
      early_finish TEXT,
      late_start TEXT,
      late_finish TEXT,
      actual_start TEXT,
      actual_finish TEXT,
      remaining_start TEXT,
      remaining_finish TEXT,
      duration_original TEXT,
      duration_remaining TEXT,
      duration_actual TEXT,
      duration_unit TEXT,
      percent_complete TEXT,
      physical_percent_complete TEXT,
      duration_percent_complete TEXT,
      calendar_id TEXT,
      calendar_name TEXT,
      constraint_type TEXT,
      constraint_date TEXT,
      deadline_date TEXT,
      deadline_variance TEXT,
      total_float TEXT,
      free_float TEXT,
      is_critical INTEGER,
      is_longest_path INTEGER,
      is_milestone INTEGER,
      assigned_company_id TEXT,
      assigned_company_name_redacted TEXT,
      crew_size TEXT,
      notes_summary_hash TEXT,
      cost_account_id TEXT,
      cost_code TEXT,
      cost_code_raw TEXT,
      cost_loaded_amount TEXT,
      cost_loaded_quantity TEXT,
      cost_loaded_unit_cost TEXT,
      cost_loaded_source_type TEXT,
      cost_loaded_confidence TEXT,
      raw_json_redacted TEXT,
      raw_source_fields_json TEXT,
      source_row_hash TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (import_id) REFERENCES schedule_file_imports(import_id),
      UNIQUE (schedule_version_key, activity_id, import_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_activities_project ON procore_ep_schedule_activities(project_key);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_activities_version ON procore_ep_schedule_activities(schedule_version_key);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_activities_import ON procore_ep_schedule_activities(import_id);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_activities_schedule ON procore_ep_schedule_activities(schedule_id);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_activities_cost_code ON procore_ep_schedule_activities(cost_code);",
    """
    CREATE TABLE IF NOT EXISTS procore_ep_schedule_relationships (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      schedule_table_id TEXT,
      schedule_id TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      predecessor_activity_id TEXT NOT NULL,
      successor_activity_id TEXT NOT NULL,
      relationship_type TEXT,
      lag_value TEXT,
      lag_unit TEXT,
      source_relationship_object_id TEXT,
      raw_json_redacted TEXT,
      source_row_hash TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (import_id) REFERENCES schedule_file_imports(import_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_relationships_version ON procore_ep_schedule_relationships(schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS procore_ep_schedule_wbs_nodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      schedule_table_id TEXT,
      schedule_id TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      wbs_id TEXT NOT NULL,
      parent_wbs_id TEXT,
      wbs_code TEXT,
      wbs_name TEXT,
      wbs_path TEXT,
      sequence_order INTEGER,
      source_object_id TEXT,
      raw_json_redacted TEXT,
      FOREIGN KEY (import_id) REFERENCES schedule_file_imports(import_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_wbs_version ON procore_ep_schedule_wbs_nodes(schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS procore_ep_schedule_calendars (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      schedule_table_id TEXT,
      schedule_id TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      calendar_id TEXT NOT NULL,
      calendar_name TEXT,
      calendar_type TEXT,
      hours_per_day TEXT,
      days_per_week TEXT,
      is_default INTEGER,
      raw_json_redacted TEXT,
      FOREIGN KEY (import_id) REFERENCES schedule_file_imports(import_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_calendars_version ON procore_ep_schedule_calendars(schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS procore_ep_schedule_activity_code_assignments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      schedule_table_id TEXT,
      schedule_id TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      activity_id TEXT NOT NULL,
      code_type TEXT,
      code_value TEXT,
      code_description TEXT,
      source_object_id TEXT,
      FOREIGN KEY (import_id) REFERENCES schedule_file_imports(import_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_codes_version ON procore_ep_schedule_activity_code_assignments(schedule_version_key);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_codes_activity ON procore_ep_schedule_activity_code_assignments(activity_id);",
    """
    CREATE TABLE IF NOT EXISTS procore_ep_schedule_udf_values (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      schedule_table_id TEXT,
      schedule_id TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      activity_id TEXT NOT NULL,
      udf_type_name TEXT,
      udf_data_type TEXT,
      udf_value TEXT,
      source_object_id TEXT,
      FOREIGN KEY (import_id) REFERENCES schedule_file_imports(import_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_udfs_version ON procore_ep_schedule_udf_values(schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_version_diffs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      from_schedule_version_key TEXT NOT NULL,
      to_schedule_version_key TEXT NOT NULL,
      diff_type TEXT,
      summary_json TEXT,
      activity_added_count INTEGER NOT NULL DEFAULT 0,
      activity_removed_count INTEGER NOT NULL DEFAULT 0,
      activity_changed_count INTEGER NOT NULL DEFAULT 0,
      relationship_added_count INTEGER NOT NULL DEFAULT 0,
      relationship_removed_count INTEGER NOT NULL DEFAULT 0,
      logic_churn_rate TEXT,
      wbs_churn_count INTEGER NOT NULL DEFAULT 0,
      calendar_churn_count INTEGER NOT NULL DEFAULT 0,
      code_churn_count INTEGER NOT NULL DEFAULT 0,
      finish_drift_days TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_diffs_project ON schedule_version_diffs(project_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_quality_findings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT,
      finding_type TEXT NOT NULL,
      severity TEXT NOT NULL,
      activity_id TEXT,
      relationship_id TEXT,
      wbs_id TEXT,
      finding_code TEXT NOT NULL,
      finding_summary TEXT NOT NULL,
      evidence_json TEXT,
      requires_operator_review INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_quality_version ON schedule_quality_findings(schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_cost_mapping_runs (
      mapping_run_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      operator_objective TEXT NOT NULL CHECK(operator_objective IN (
        'association_only', 'simplified_duration_distribution',
        'true_cost_loading', 'existing_cost_loaded_review'
      )),
      financial_value_source TEXT,
      distribution_method TEXT,
      cost_loaded_status_at_start TEXT,
      mapping_status TEXT NOT NULL DEFAULT 'pending' CHECK(mapping_status IN (
        'pending', 'in_review', 'approved', 'rejected'
      )),
      created_by_operator TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      approved_at TEXT,
      evidence_package_id TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_mapping_runs_project ON schedule_cost_mapping_runs(project_key);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_mapping_runs_version ON schedule_cost_mapping_runs(schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_cost_mapping_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      mapping_run_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      activity_id TEXT NOT NULL,
      candidate_cost_code TEXT,
      candidate_budget_code_key TEXT,
      candidate_source TEXT,
      confidence_score TEXT,
      evidence_json TEXT,
      ai_assisted INTEGER NOT NULL DEFAULT 0,
      operator_status TEXT NOT NULL DEFAULT 'pending' CHECK(operator_status IN (
        'pending', 'approved', 'rejected', 'edited', 'not_applicable'
      )),
      operator_notes_redacted TEXT,
      reviewed_at TEXT,
      reviewed_by_operator TEXT,
      FOREIGN KEY (mapping_run_id) REFERENCES schedule_cost_mapping_runs(mapping_run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_candidates_run ON schedule_cost_mapping_candidates(mapping_run_id);",
    """
    CREATE TABLE IF NOT EXISTS schedule_cost_distributions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      mapping_run_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      activity_id TEXT NOT NULL,
      budget_code_key TEXT,
      cost_code TEXT,
      allocation_method TEXT NOT NULL CHECK(allocation_method IN (
        'duration_weighted', 'equal_split', 'manual_percent', 'true_cost_loaded',
        'analytical_distribution'
      )),
      source_financial_record_type TEXT,
      source_financial_record_id TEXT,
      source_value TEXT,
      allocation_percent TEXT,
      allocated_value TEXT,
      operator_approved INTEGER NOT NULL DEFAULT 0,
      reconciliation_status TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (mapping_run_id) REFERENCES schedule_cost_mapping_runs(mapping_run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_distributions_run ON schedule_cost_distributions(mapping_run_id);",
    """
    CREATE TABLE IF NOT EXISTS schedule_cost_weighting_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      mapping_run_id TEXT NOT NULL,
      budget_code_key TEXT,
      schedule_risk_score TEXT,
      mapping_confidence TEXT,
      forecast_confidence_modifier TEXT,
      risk_reasons_json TEXT,
      supporting_activity_count INTEGER NOT NULL DEFAULT 0,
      unmapped_activity_count INTEGER NOT NULL DEFAULT 0,
      operator_review_required INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (mapping_run_id) REFERENCES schedule_cost_mapping_runs(mapping_run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_weighting_project ON schedule_cost_weighting_results(project_key);",
]