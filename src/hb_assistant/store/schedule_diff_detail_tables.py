"""V79 detailed schedule version diff fact table."""

from __future__ import annotations

V79_TABLES: tuple[str, ...] = ("schedule_version_diff_detail_facts",)

V79_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_version_diff_detail_facts (
      detail_id TEXT PRIMARY KEY,
      diff_id INTEGER NOT NULL,
      project_key TEXT NOT NULL,
      from_schedule_version_key TEXT NOT NULL,
      to_schedule_version_key TEXT NOT NULL,
      schedule_identity_key TEXT,
      identity_safe INTEGER NOT NULL DEFAULT 0,
      comparison_type TEXT NOT NULL DEFAULT 'manual',
      change_domain TEXT NOT NULL,
      change_type TEXT NOT NULL,
      entity_key TEXT,
      entity_label TEXT,
      wbs_code TEXT,
      wbs_name TEXT,
      activity_id TEXT,
      activity_name TEXT,
      predecessor_activity_id TEXT,
      successor_activity_id TEXT,
      field_name TEXT,
      from_value TEXT,
      to_value TEXT,
      numeric_delta TEXT,
      day_delta INTEGER,
      severity TEXT NOT NULL DEFAULT 'informational',
      significance_score TEXT,
      is_critical_path_related INTEGER NOT NULL DEFAULT 0,
      is_open_end_related INTEGER NOT NULL DEFAULT 0,
      requires_attention INTEGER NOT NULL DEFAULT 0,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_detail_diff
    ON schedule_version_diff_detail_facts(diff_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_detail_project
    ON schedule_version_diff_detail_facts(project_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_detail_domain_type
    ON schedule_version_diff_detail_facts(change_domain, change_type);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_detail_activity
    ON schedule_version_diff_detail_facts(activity_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_detail_severity
    ON schedule_version_diff_detail_facts(severity);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_detail_requires_attention
    ON schedule_version_diff_detail_facts(requires_attention);
    """,
]
