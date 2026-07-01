"""v97 Project Schedule Hub named baseline review item persistence (additive)."""

from __future__ import annotations

V97_TABLES: tuple[str, ...] = (
    "project_schedule_named_baseline_review_items",
    "project_schedule_named_baseline_review_item_events",
)

REVIEW_SCOPE_NAMED_BASELINE = "named_baseline"

V97_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS project_schedule_named_baseline_review_items (
      review_item_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      review_scope TEXT NOT NULL DEFAULT 'named_baseline',
      current_schedule_version_key TEXT NOT NULL,
      comparison_basis TEXT NOT NULL,
      baseline_slot_key TEXT NOT NULL,
      baseline_slot_label TEXT,
      baseline_selection_id TEXT,
      baseline_schedule_version_key TEXT NOT NULL,
      baseline_schedule_data_date TEXT,
      baseline_display_name TEXT,
      schedule_data_date TEXT,
      as_of_date TEXT,
      source_stable_key TEXT NOT NULL,
      source_metric_key TEXT NOT NULL,
      source_signal_type TEXT NOT NULL,
      source_activity_id TEXT,
      item_type TEXT NOT NULL,
      item_title TEXT NOT NULL,
      priority INTEGER NOT NULL DEFAULT 50,
      review_status TEXT NOT NULL DEFAULT 'open'
        CHECK(review_status IN ('open', 'reviewed', 'dismissed', 'watching')),
      pm_notes TEXT,
      evidence_json TEXT,
      reviewed_by_operator TEXT,
      reviewed_at TEXT,
      last_seen_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ps_named_baseline_review_identity
    ON project_schedule_named_baseline_review_items(
      project_key,
      current_schedule_version_key,
      comparison_basis,
      baseline_schedule_version_key,
      source_stable_key,
      source_metric_key,
      source_signal_type,
      COALESCE(source_activity_id, '')
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ps_named_baseline_review_project_scope
    ON project_schedule_named_baseline_review_items(
      project_key,
      comparison_basis,
      baseline_schedule_version_key,
      current_schedule_version_key
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS project_schedule_named_baseline_review_item_events (
      event_id TEXT PRIMARY KEY,
      review_item_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      current_schedule_version_key TEXT NOT NULL,
      event_type TEXT NOT NULL
        CHECK(event_type IN ('created', 'synced', 'status_changed', 'notes_changed')),
      prior_status TEXT,
      new_status TEXT,
      prior_notes TEXT,
      new_notes TEXT,
      operator_id TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ps_named_baseline_review_events_item
    ON project_schedule_named_baseline_review_item_events(review_item_id, created_at);
    """,
]
