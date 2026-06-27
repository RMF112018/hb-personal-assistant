"""V79 schedule version diff impact rollup table."""

from __future__ import annotations

V79_TABLES: tuple[str, ...] = ("schedule_version_diff_impact_rollups",)

V79_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_version_diff_impact_rollups (
      rollup_id TEXT PRIMARY KEY,
      diff_id INTEGER NOT NULL,
      project_key TEXT NOT NULL,
      from_schedule_version_key TEXT NOT NULL,
      to_schedule_version_key TEXT NOT NULL,
      schedule_identity_key TEXT,
      comparison_type TEXT,
      identity_safe INTEGER NOT NULL DEFAULT 0,
      rollup_type TEXT NOT NULL,
      rollup_key TEXT NOT NULL,
      rollup_label TEXT,
      wbs_code TEXT,
      wbs_name TEXT,
      activity_id TEXT,
      activity_name TEXT,
      milestone_activity_id TEXT,
      milestone_name TEXT,
      activity_count INTEGER NOT NULL DEFAULT 0,
      change_count INTEGER NOT NULL DEFAULT 0,
      critical_count INTEGER NOT NULL DEFAULT 0,
      major_count INTEGER NOT NULL DEFAULT 0,
      moderate_count INTEGER NOT NULL DEFAULT 0,
      minor_count INTEGER NOT NULL DEFAULT 0,
      informational_count INTEGER NOT NULL DEFAULT 0,
      date_drift_count INTEGER NOT NULL DEFAULT 0,
      logic_change_count INTEGER NOT NULL DEFAULT 0,
      relationship_change_count INTEGER NOT NULL DEFAULT 0,
      activity_added_count INTEGER NOT NULL DEFAULT 0,
      activity_removed_count INTEGER NOT NULL DEFAULT 0,
      requires_attention_count INTEGER NOT NULL DEFAULT 0,
      max_day_delta INTEGER,
      net_day_delta INTEGER,
      max_later_day_delta INTEGER,
      max_earlier_day_delta INTEGER,
      impact_score TEXT,
      impact_level TEXT NOT NULL DEFAULT 'informational',
      requires_attention INTEGER NOT NULL DEFAULT 0,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_diff
    ON schedule_version_diff_impact_rollups(diff_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_project
    ON schedule_version_diff_impact_rollups(project_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_type
    ON schedule_version_diff_impact_rollups(rollup_type);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_identity_safe
    ON schedule_version_diff_impact_rollups(identity_safe);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_attention
    ON schedule_version_diff_impact_rollups(requires_attention);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_impact_level
    ON schedule_version_diff_impact_rollups(impact_level);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_wbs
    ON schedule_version_diff_impact_rollups(wbs_code);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_diff_impact_rollups_activity
    ON schedule_version_diff_impact_rollups(activity_id);
    """,
]
