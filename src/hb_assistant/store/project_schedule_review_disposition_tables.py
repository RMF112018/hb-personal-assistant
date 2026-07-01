"""V98 Phase 17 review disposition expansion (table rebuild + data migration)."""

from __future__ import annotations

V98_TABLES: tuple[str, ...] = (
    "project_schedule_review_items",
    "project_schedule_review_item_events",
    "project_schedule_named_baseline_review_items",
    "project_schedule_named_baseline_review_item_events",
)

_DISPOSITION_CHECK = """
CHECK(review_status IN (
  'needs_review',
  'accepted_for_follow_up',
  'dismissed_not_material',
  'superseded',
  'duplicate',
  'resolved',
  'blocked_by_identity',
  'blocked_by_trust'
))
"""

_EVENT_TYPE_CHECK = """
CHECK(event_type IN (
  'created',
  'synced',
  'status_changed',
  'notes_changed',
  'carried_forward',
  'promoted'
))
"""

_NAMED_EVENT_TYPE_CHECK = """
CHECK(event_type IN (
  'created',
  'synced',
  'status_changed',
  'notes_changed',
  'promoted'
))
"""

_STATUS_MIGRATION_CASE = """
CASE review_status
  WHEN 'open' THEN 'needs_review'
  WHEN 'watching' THEN 'needs_review'
  WHEN 'reviewed' THEN 'accepted_for_follow_up'
  WHEN 'dismissed' THEN 'dismissed_not_material'
  ELSE review_status
END
"""

V98_STATEMENTS: list[str] = [
    # --- Standard review items ---
    """
    CREATE TABLE project_schedule_review_items_v98 (
      review_item_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      stable_item_key TEXT NOT NULL,
      item_type TEXT NOT NULL,
      item_title TEXT NOT NULL,
      priority INTEGER NOT NULL DEFAULT 50,
      review_status TEXT NOT NULL DEFAULT 'needs_review'
        CHECK(review_status IN (
          'needs_review',
          'accepted_for_follow_up',
          'dismissed_not_material',
          'superseded',
          'duplicate',
          'resolved',
          'blocked_by_identity',
          'blocked_by_trust'
        )),
      disposition_reason TEXT,
      pm_notes TEXT,
      evidence_json TEXT,
      source_activity_id TEXT,
      reviewed_by_operator TEXT,
      reviewed_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    f"""
    INSERT INTO project_schedule_review_items_v98 (
      review_item_id, project_key, schedule_version_key, stable_item_key,
      item_type, item_title, priority, review_status, disposition_reason,
      pm_notes, evidence_json, source_activity_id, reviewed_by_operator,
      reviewed_at, created_at, updated_at
    )
    SELECT
      review_item_id, project_key, schedule_version_key, stable_item_key,
      item_type, item_title, priority,
      {_STATUS_MIGRATION_CASE},
      NULL,
      pm_notes, evidence_json, source_activity_id, reviewed_by_operator,
      reviewed_at, created_at, updated_at
    FROM project_schedule_review_items;
    """,
    "DROP TABLE project_schedule_review_items;",
    "ALTER TABLE project_schedule_review_items_v98 RENAME TO project_schedule_review_items;",
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
    # --- Standard review events ---
    """
    CREATE TABLE project_schedule_review_item_events_v98 (
      event_id TEXT PRIMARY KEY,
      review_item_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      event_type TEXT NOT NULL
        CHECK(event_type IN (
          'created', 'synced', 'status_changed', 'notes_changed',
          'carried_forward', 'promoted'
        )),
      prior_status TEXT,
      new_status TEXT,
      prior_notes TEXT,
      new_notes TEXT,
      disposition_reason TEXT,
      operator_id TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    INSERT INTO project_schedule_review_item_events_v98 (
      event_id, review_item_id, project_key, schedule_version_key,
      event_type, prior_status, new_status, prior_notes, new_notes,
      disposition_reason, operator_id, created_at
    )
    SELECT
      event_id, review_item_id, project_key, schedule_version_key,
      event_type, prior_status, new_status, prior_notes, new_notes,
      NULL, operator_id, created_at
    FROM project_schedule_review_item_events;
    """,
    "DROP TABLE project_schedule_review_item_events;",
    "ALTER TABLE project_schedule_review_item_events_v98 RENAME TO project_schedule_review_item_events;",
    """
    CREATE INDEX IF NOT EXISTS idx_project_schedule_review_item_events_item
    ON project_schedule_review_item_events(review_item_id, created_at);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_schedule_review_item_events_project
    ON project_schedule_review_item_events(project_key, schedule_version_key);
    """,
    # --- Named baseline review items ---
    """
    CREATE TABLE project_schedule_named_baseline_review_items_v98 (
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
      review_status TEXT NOT NULL DEFAULT 'needs_review'
        CHECK(review_status IN (
          'needs_review',
          'accepted_for_follow_up',
          'dismissed_not_material',
          'superseded',
          'duplicate',
          'resolved',
          'blocked_by_identity',
          'blocked_by_trust'
        )),
      disposition_reason TEXT,
      pm_notes TEXT,
      evidence_json TEXT,
      reviewed_by_operator TEXT,
      reviewed_at TEXT,
      last_seen_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    f"""
    INSERT INTO project_schedule_named_baseline_review_items_v98 (
      review_item_id, project_key, review_scope, current_schedule_version_key,
      comparison_basis, baseline_slot_key, baseline_slot_label, baseline_selection_id,
      baseline_schedule_version_key, baseline_schedule_data_date, baseline_display_name,
      schedule_data_date, as_of_date, source_stable_key, source_metric_key,
      source_signal_type, source_activity_id, item_type, item_title, priority,
      review_status, disposition_reason, pm_notes, evidence_json,
      reviewed_by_operator, reviewed_at, last_seen_at, created_at, updated_at
    )
    SELECT
      review_item_id, project_key, review_scope, current_schedule_version_key,
      comparison_basis, baseline_slot_key, baseline_slot_label, baseline_selection_id,
      baseline_schedule_version_key, baseline_schedule_data_date, baseline_display_name,
      schedule_data_date, as_of_date, source_stable_key, source_metric_key,
      source_signal_type, source_activity_id, item_type, item_title, priority,
      {_STATUS_MIGRATION_CASE},
      NULL, pm_notes, evidence_json,
      reviewed_by_operator, reviewed_at, last_seen_at, created_at, updated_at
    FROM project_schedule_named_baseline_review_items;
    """,
    "DROP TABLE project_schedule_named_baseline_review_items;",
    "ALTER TABLE project_schedule_named_baseline_review_items_v98 RENAME TO project_schedule_named_baseline_review_items;",
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
    # --- Named baseline review events ---
    """
    CREATE TABLE project_schedule_named_baseline_review_item_events_v98 (
      event_id TEXT PRIMARY KEY,
      review_item_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      current_schedule_version_key TEXT NOT NULL,
      event_type TEXT NOT NULL
        CHECK(event_type IN (
          'created', 'synced', 'status_changed', 'notes_changed', 'promoted'
        )),
      prior_status TEXT,
      new_status TEXT,
      prior_notes TEXT,
      new_notes TEXT,
      disposition_reason TEXT,
      operator_id TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    INSERT INTO project_schedule_named_baseline_review_item_events_v98 (
      event_id, review_item_id, project_key, current_schedule_version_key,
      event_type, prior_status, new_status, prior_notes, new_notes,
      disposition_reason, operator_id, created_at
    )
    SELECT
      event_id, review_item_id, project_key, current_schedule_version_key,
      event_type, prior_status, new_status, prior_notes, new_notes,
      NULL, operator_id, created_at
    FROM project_schedule_named_baseline_review_item_events;
    """,
    "DROP TABLE project_schedule_named_baseline_review_item_events;",
    "ALTER TABLE project_schedule_named_baseline_review_item_events_v98 RENAME TO project_schedule_named_baseline_review_item_events;",
    """
    CREATE INDEX IF NOT EXISTS idx_ps_named_baseline_review_events_item
    ON project_schedule_named_baseline_review_item_events(review_item_id, created_at);
    """,
]
