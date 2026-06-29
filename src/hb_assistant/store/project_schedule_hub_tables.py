"""V90 Project Schedule Hub Phase 2 tables: series membership and baseline selection."""

from __future__ import annotations

V90_TABLES: tuple[str, ...] = (
    "project_schedule_series_membership",
    "project_schedule_baseline_selections",
)

V90_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS project_schedule_series_membership (
      membership_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT,
      membership_status TEXT NOT NULL DEFAULT 'pending_review',
      review_reason TEXT,
      reviewed_by_operator TEXT,
      reviewed_at TEXT,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_project_schedule_series_membership_version
    ON project_schedule_series_membership(project_key, schedule_version_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_schedule_series_membership_project_status
    ON project_schedule_series_membership(project_key, membership_status);
    """,
    """
    CREATE TABLE IF NOT EXISTS project_schedule_baseline_selections (
      selection_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      current_schedule_version_key TEXT NOT NULL,
      selected_baseline_schedule_version_key TEXT NOT NULL,
      selection_status TEXT NOT NULL DEFAULT 'active',
      selected_by_operator TEXT,
      selected_at TEXT,
      selection_note TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_project_schedule_baseline_active
    ON project_schedule_baseline_selections(
      project_key, current_schedule_version_key, selection_status
    )
    WHERE selection_status='active';
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_schedule_baseline_project
    ON project_schedule_baseline_selections(project_key, current_schedule_version_key);
    """,
]

V91_TABLES: tuple[str, ...] = ("project_schedule_review_items",)

V91_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS project_schedule_review_items (
      review_item_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      stable_item_key TEXT NOT NULL,
      item_type TEXT NOT NULL,
      item_title TEXT NOT NULL,
      priority INTEGER NOT NULL DEFAULT 50,
      review_status TEXT NOT NULL DEFAULT 'open'
        CHECK(review_status IN ('open', 'reviewed', 'dismissed', 'watching')),
      pm_notes TEXT,
      evidence_json TEXT,
      source_activity_id TEXT,
      reviewed_by_operator TEXT,
      reviewed_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_project_schedule_review_items_version_key
    ON project_schedule_review_items(project_key, schedule_version_key, stable_item_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_schedule_review_items_project_status
    ON project_schedule_review_items(project_key, review_status);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_schedule_review_items_stable_key
    ON project_schedule_review_items(project_key, stable_item_key);
    """,
]