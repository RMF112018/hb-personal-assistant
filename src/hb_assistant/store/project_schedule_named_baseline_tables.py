"""v96 Project Schedule Hub named baseline slot selections (additive)."""

from __future__ import annotations

V96_TABLES: tuple[str, ...] = ("project_schedule_named_baseline_slots",)

V96_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS project_schedule_named_baseline_slots (
      selection_id TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      slot_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      display_name TEXT,
      notes TEXT,
      selected_by TEXT,
      selected_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      is_active INTEGER NOT NULL DEFAULT 1
    );
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_project_schedule_named_baseline_active_slot
    ON project_schedule_named_baseline_slots(project_key, slot_key)
    WHERE is_active = 1;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_schedule_named_baseline_project
    ON project_schedule_named_baseline_slots(project_key, is_active);
    """,
]
