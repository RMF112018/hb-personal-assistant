"""V83 CPM graph diagnostics foundation tables (additive).

Two additive tables persist the structural graph diagnostics produced by
``schedule_cpm_graph.build_graph`` for one schedule version:

- ``schedule_cpm_runs`` — one summary row per graph-diagnostics run (node/edge counts,
  acyclic flag, deterministic topological order, and explicit ``cpm_recalculation_status``
  so the persisted record states CPM recalculation is not implemented in this phase).
- ``schedule_cpm_diagnostics`` — one row per structural finding (missing/self/duplicate/
  unsupported edges, open ends, cycle).

These tables hold NO computed CPM dates, float, or critical/longest-path designations.
All statements are ``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS`` and are
therefore idempotent.
"""

from __future__ import annotations

V83_TABLES: tuple[str, ...] = (
    "schedule_cpm_runs",
    "schedule_cpm_diagnostics",
)

V83_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_cpm_runs (
        cpm_run_id TEXT PRIMARY KEY,
        project_key TEXT NOT NULL,
        schedule_version_key TEXT NOT NULL,
        import_id TEXT NOT NULL,
        node_count INTEGER NOT NULL DEFAULT 0,
        edge_count INTEGER NOT NULL DEFAULT 0,
        is_acyclic INTEGER NOT NULL DEFAULT 1,
        diagnostic_count INTEGER NOT NULL DEFAULT 0,
        topological_order_json TEXT,
        analysis_scope TEXT NOT NULL DEFAULT 'graph_diagnostics_only',
        cpm_recalculation_status TEXT NOT NULL DEFAULT 'not_implemented',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_runs_version "
    "ON schedule_cpm_runs(schedule_version_key)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_runs_project "
    "ON schedule_cpm_runs(project_key)",
    """
    CREATE TABLE IF NOT EXISTS schedule_cpm_diagnostics (
        diagnostic_id TEXT PRIMARY KEY,
        cpm_run_id TEXT NOT NULL,
        project_key TEXT NOT NULL,
        schedule_version_key TEXT NOT NULL,
        import_id TEXT NOT NULL,
        activity_id TEXT,
        relationship_ref TEXT,
        diagnostic_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        summary TEXT NOT NULL,
        evidence_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cpm_run_id) REFERENCES schedule_cpm_runs(cpm_run_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_diagnostics_run "
    "ON schedule_cpm_diagnostics(cpm_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_diagnostics_version "
    "ON schedule_cpm_diagnostics(schedule_version_key)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_diagnostics_activity "
    "ON schedule_cpm_diagnostics(activity_id)",
]
