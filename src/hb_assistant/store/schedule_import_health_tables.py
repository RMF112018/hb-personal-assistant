"""V75 schedule import health foundation tables.

Additive package, capability, baseline, crosswalk, health-fact, and diff-fact
tables for package-aware schedule imports. Existing V62-V74 schedule/forecast
tables are not renamed, dropped, or repurposed.
"""

from __future__ import annotations

V75_TABLES: tuple[str, ...] = (
    "schedule_import_packages",
    "schedule_import_package_files",
    "schedule_source_capabilities",
    "schedule_baseline_projects",
    "schedule_baseline_activities",
    "schedule_baseline_relationships",
    "schedule_baseline_wbs",
    "schedule_baseline_activity_codes",
    "schedule_baseline_udfs",
    "schedule_baseline_activity_crosswalk",
    "schedule_baseline_health_facts",
    "schedule_version_diff_facts",
)

V75_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_import_packages (
      package_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      package_mode TEXT NOT NULL,
      selected_current_schedule_version_key TEXT,
      selected_current_project_object_id TEXT,
      selected_current_project_id TEXT,
      selected_current_project_name TEXT,
      status TEXT NOT NULL DEFAULT 'previewed',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      committed_at TEXT,
      manifest_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_import_packages_import ON schedule_import_packages(import_id);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_import_packages_version ON schedule_import_packages(selected_current_schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_import_package_files (
      package_file_id TEXT PRIMARY KEY,
      package_id TEXT NOT NULL,
      import_id TEXT NOT NULL,
      filename TEXT NOT NULL,
      source_format TEXT,
      source_vendor TEXT,
      file_role TEXT NOT NULL DEFAULT 'unknown',
      sha256 TEXT,
      byte_size INTEGER NOT NULL DEFAULT 0,
      parse_status TEXT NOT NULL DEFAULT 'parsed',
      parser_name TEXT,
      parser_version TEXT,
      detected_project_count INTEGER NOT NULL DEFAULT 0,
      detected_baseline_project_count INTEGER NOT NULL DEFAULT 0,
      detected_activity_count INTEGER NOT NULL DEFAULT 0,
      detected_relationship_count INTEGER NOT NULL DEFAULT 0,
      coverage_json TEXT,
      warnings_json TEXT,
      FOREIGN KEY (package_id) REFERENCES schedule_import_packages(package_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_import_package_files_package ON schedule_import_package_files(package_id);",
    """
    CREATE TABLE IF NOT EXISTS schedule_source_capabilities (
      capability_id TEXT PRIMARY KEY,
      package_id TEXT,
      schedule_version_key TEXT,
      source_format TEXT,
      capability_key TEXT NOT NULL,
      capability_status TEXT NOT NULL CHECK(capability_status IN (
        'available', 'partially_available', 'unavailable', 'not_applicable',
        'requires_companion_file', 'requires_user_mapping', 'conflict_detected',
        'deferred'
      )),
      source_file_id TEXT,
      basis TEXT,
      unavailable_reason TEXT,
      recommended_action TEXT,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_capabilities_version ON schedule_source_capabilities(schedule_version_key);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_capabilities_package ON schedule_source_capabilities(package_id);",
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_projects (
      baseline_project_key TEXT PRIMARY KEY,
      package_id TEXT NOT NULL,
      import_id TEXT NOT NULL,
      current_schedule_version_key TEXT NOT NULL,
      current_project_object_id TEXT,
      baseline_project_object_id TEXT,
      baseline_project_id TEXT,
      baseline_project_name TEXT,
      original_project_object_id TEXT,
      baseline_type_object_id TEXT,
      baseline_type_name TEXT,
      baseline_data_date TEXT,
      planned_start TEXT,
      scheduled_finish TEXT,
      source_format TEXT,
      source_file_id TEXT,
      activity_count INTEGER NOT NULL DEFAULT 0,
      relationship_count INTEGER NOT NULL DEFAULT 0,
      wbs_count INTEGER NOT NULL DEFAULT 0,
      raw_metadata_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_baseline_projects_version ON schedule_baseline_projects(current_schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_activities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      baseline_project_key TEXT NOT NULL,
      package_id TEXT NOT NULL,
      import_id TEXT NOT NULL,
      current_schedule_version_key TEXT NOT NULL,
      baseline_project_object_id TEXT,
      activity_id TEXT NOT NULL,
      source_activity_object_id TEXT,
      activity_name TEXT,
      activity_type TEXT,
      activity_status TEXT,
      wbs_id TEXT,
      wbs_code TEXT,
      wbs_path TEXT,
      calendar_id TEXT,
      planned_start TEXT,
      planned_finish TEXT,
      start_date TEXT,
      finish_date TEXT,
      actual_start TEXT,
      actual_finish TEXT,
      remaining_early_start TEXT,
      remaining_early_finish TEXT,
      remaining_late_start TEXT,
      remaining_late_finish TEXT,
      early_start TEXT,
      early_finish TEXT,
      late_start TEXT,
      late_finish TEXT,
      duration_original TEXT,
      duration_remaining TEXT,
      duration_actual TEXT,
      percent_complete TEXT,
      physical_percent_complete TEXT,
      duration_percent_complete TEXT,
      constraint_type TEXT,
      constraint_date TEXT,
      secondary_constraint_type TEXT,
      secondary_constraint_date TEXT,
      deadline_date TEXT,
      is_critical INTEGER,
      is_longest_path INTEGER,
      total_float TEXT,
      free_float TEXT,
      cost_code TEXT,
      cost_loaded_amount TEXT,
      cost_loaded_source_type TEXT,
      raw_source_fields_json TEXT,
      source_row_hash TEXT,
      FOREIGN KEY (baseline_project_key) REFERENCES schedule_baseline_projects(baseline_project_key)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_baseline_activities_project ON schedule_baseline_activities(baseline_project_key);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_baseline_activities_version ON schedule_baseline_activities(current_schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_relationships (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      baseline_project_key TEXT NOT NULL,
      package_id TEXT NOT NULL,
      import_id TEXT NOT NULL,
      current_schedule_version_key TEXT NOT NULL,
      baseline_project_object_id TEXT,
      predecessor_activity_id TEXT NOT NULL,
      successor_activity_id TEXT NOT NULL,
      relationship_type TEXT,
      lag_value TEXT,
      lag_unit TEXT,
      source_relationship_object_id TEXT,
      raw_source_fields_json TEXT,
      source_row_hash TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_baseline_relationships_project ON schedule_baseline_relationships(baseline_project_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_wbs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      baseline_project_key TEXT NOT NULL,
      wbs_id TEXT NOT NULL,
      parent_wbs_id TEXT,
      wbs_code TEXT,
      wbs_name TEXT,
      wbs_path TEXT,
      sequence_order INTEGER,
      source_object_id TEXT,
      raw_json_redacted TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_activity_codes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      baseline_project_key TEXT NOT NULL,
      activity_id TEXT NOT NULL,
      code_type TEXT,
      code_value TEXT,
      code_description TEXT,
      source_object_id TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_udfs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      baseline_project_key TEXT NOT NULL,
      activity_id TEXT NOT NULL,
      udf_type_name TEXT,
      udf_data_type TEXT,
      udf_value TEXT,
      source_object_id TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_activity_crosswalk (
      crosswalk_id TEXT PRIMARY KEY,
      current_schedule_version_key TEXT NOT NULL,
      baseline_project_key TEXT NOT NULL,
      current_activity_id TEXT,
      baseline_activity_id TEXT,
      current_activity_object_id TEXT,
      baseline_activity_object_id TEXT,
      match_method TEXT NOT NULL,
      match_confidence TEXT NOT NULL,
      name_similarity TEXT,
      wbs_match INTEGER,
      duration_match INTEGER,
      date_proximity_score TEXT,
      review_required INTEGER NOT NULL DEFAULT 0,
      review_status TEXT NOT NULL DEFAULT 'not_reviewed',
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_baseline_crosswalk_version ON schedule_baseline_activity_crosswalk(current_schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_baseline_health_facts (
      fact_id TEXT PRIMARY KEY,
      current_schedule_version_key TEXT NOT NULL,
      baseline_project_key TEXT NOT NULL,
      metric_key TEXT NOT NULL,
      metric_value TEXT,
      metric_unit TEXT,
      status TEXT NOT NULL,
      basis TEXT,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_baseline_health_facts_version ON schedule_baseline_health_facts(current_schedule_version_key);",
    """
    CREATE TABLE IF NOT EXISTS schedule_version_diff_facts (
      diff_fact_id TEXT PRIMARY KEY,
      diff_id INTEGER,
      project_key TEXT NOT NULL,
      from_schedule_version_key TEXT,
      to_schedule_version_key TEXT NOT NULL,
      metric_key TEXT NOT NULL,
      metric_value TEXT,
      metric_unit TEXT,
      status TEXT NOT NULL,
      basis TEXT,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_version_diff_facts_to_version ON schedule_version_diff_facts(to_schedule_version_key);",
]
