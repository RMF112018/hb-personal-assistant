"""V95 CPM import observability (additive).

Durable per-import CPM recompute metadata: canonical input counts, graph sizing,
status/timing, and failure details for import commit and manual retry paths.
"""

from __future__ import annotations

V95_TABLES: tuple[str, ...] = ("schedule_cpm_import_observability",)

V95_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_cpm_import_observability (
      cpm_import_observability_id TEXT PRIMARY KEY,
      import_id TEXT NOT NULL,
      package_id TEXT,
      schedule_version_key TEXT NOT NULL,
      trigger_source TEXT NOT NULL DEFAULT 'import_commit',
      canonical_input_activity_count INTEGER NOT NULL DEFAULT 0,
      canonical_input_relationship_count INTEGER NOT NULL DEFAULT 0,
      graph_node_count INTEGER,
      graph_edge_count INTEGER,
      status TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT NOT NULL,
      duration_ms INTEGER NOT NULL DEFAULT 0,
      warning_count INTEGER NOT NULL DEFAULT 0,
      error_count INTEGER NOT NULL DEFAULT 0,
      failure_code TEXT,
      failure_message TEXT,
      failed_step TEXT,
      cpm_run_id TEXT,
      diagnostics_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_cpm_import_obs_import "
    "ON schedule_cpm_import_observability(import_id);",
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_import_obs_version "
    "ON schedule_cpm_import_observability(schedule_version_key);",
]
