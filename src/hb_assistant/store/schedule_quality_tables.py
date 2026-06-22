"""V64 schedule quality evaluation tables (additive)."""

from __future__ import annotations

V64_TABLES: tuple[str, ...] = (
    "schedule_quality_evaluation_runs",
    "schedule_quality_metric_results",
    "schedule_quality_scorecards",
)

V64_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_quality_evaluation_runs (
      evaluation_run_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      schedule_table_id TEXT,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT,
      assessment_profile TEXT NOT NULL,
      assessment_profile_version TEXT NOT NULL,
      method_source TEXT NOT NULL,
      trigger_source TEXT NOT NULL CHECK(trigger_source IN (
        'import_commit', 'procore_projection', 'manual_rerun', 'material_update'
      )),
      idempotency_key TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN (
        'pending', 'running', 'completed', 'failed'
      )),
      is_latest INTEGER NOT NULL DEFAULT 0,
      supersedes_run_id TEXT,
      queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      started_at TEXT,
      completed_at TEXT,
      error_code TEXT,
      error_message_redacted TEXT,
      engine_version TEXT NOT NULL,
      checker_version TEXT NOT NULL,
      UNIQUE(schedule_version_key, idempotency_key)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sq_runs_version ON schedule_quality_evaluation_runs(schedule_version_key);",
    "CREATE INDEX IF NOT EXISTS idx_sq_runs_status ON schedule_quality_evaluation_runs(status);",
    "CREATE INDEX IF NOT EXISTS idx_sq_runs_latest ON schedule_quality_evaluation_runs(schedule_version_key, is_latest);",
    """
    CREATE TABLE IF NOT EXISTS schedule_quality_metric_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      evaluation_run_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      metric_code TEXT NOT NULL,
      metric_name TEXT NOT NULL,
      metric_family TEXT NOT NULL CHECK(metric_family IN ('dcma', 'gao', 'aace', 'supplemental')),
      numerator TEXT,
      denominator TEXT,
      value TEXT,
      unit TEXT,
      threshold_warning TEXT,
      threshold_fail TEXT,
      status TEXT NOT NULL CHECK(status IN (
        'measured', 'passed_threshold', 'warning_threshold', 'failed_threshold',
        'not_measurable_missing_data', 'not_applicable'
      )),
      not_measurable_reason TEXT,
      evidence_json TEXT,
      related_finding_codes_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (evaluation_run_id) REFERENCES schedule_quality_evaluation_runs(evaluation_run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sq_metrics_run ON schedule_quality_metric_results(evaluation_run_id);",
    """
    CREATE TABLE IF NOT EXISTS schedule_quality_scorecards (
      evaluation_run_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      assessment_profile TEXT NOT NULL,
      quality_score TEXT,
      quality_grade TEXT NOT NULL,
      dcma_measured_count INTEGER NOT NULL DEFAULT 0,
      dcma_not_measurable_count INTEGER NOT NULL DEFAULT 0,
      dcma_pass_count INTEGER NOT NULL DEFAULT 0,
      dcma_warn_count INTEGER NOT NULL DEFAULT 0,
      dcma_fail_count INTEGER NOT NULL DEFAULT 0,
      gao_category_summary_json TEXT NOT NULL DEFAULT '{}',
      finding_counts_json TEXT NOT NULL DEFAULT '{}',
      downstream_readiness_json TEXT NOT NULL DEFAULT '{}',
      disclaimer_version TEXT NOT NULL DEFAULT 'sq_disclaimer_v1',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (evaluation_run_id) REFERENCES schedule_quality_evaluation_runs(evaluation_run_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sq_scorecards_version ON schedule_quality_scorecards(schedule_version_key);",
]

V64_FINDING_ALTER_COLUMNS: tuple[str, ...] = (
    "evaluation_run_id",
    "assessment_profile",
    "metric_code",
    "category",
)