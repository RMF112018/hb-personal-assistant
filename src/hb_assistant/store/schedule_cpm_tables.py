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


# ---------------------------------------------------------------------------------------
# V84 CPM forward pass foundation (additive).
#
# Two additive result tables persist the deterministic forward-pass output produced by
# ``schedule_cpm_forward_pass.compute_forward_pass`` for one schedule version:
#
# - ``schedule_cpm_activity_results`` — one row per (run, activity): computed early start /
#   early finish as both day-offsets-from-anchor (authoritative) and derived ISO datetimes,
#   plus duration provenance and a forward_pass_status.
# - ``schedule_cpm_relationship_results`` — one row per (run, relationship): how the
#   relationship constrained the successor early start (normalized lag, predecessor offsets,
#   candidate successor ES, relationship_calc_status).
#
# These tables hold NO backward-pass values, float, or critical/longest-path designations,
# and NEVER mirror or overwrite source-export schedule fields. ``schedule_cpm_runs`` is
# extended additively (see V84_RUNS_ADDITIVE_COLUMNS) with forward-pass run metadata.
# ---------------------------------------------------------------------------------------

V84_TABLES: tuple[str, ...] = (
    "schedule_cpm_activity_results",
    "schedule_cpm_relationship_results",
)

# Column name -> column type/constraint, added to the existing schedule_cpm_runs table via a
# column-existence-guarded reconcile (ALTER TABLE ADD COLUMN is not IF NOT EXISTS in SQLite).
# node_count / edge_count already exist and double as activity/relationship counts.
V84_RUNS_ADDITIVE_COLUMNS: dict[str, str] = {
    "calculation_type": "TEXT NOT NULL DEFAULT 'graph_diagnostics'",
    "schedule_start_anchor": "TEXT",
    "schedule_start_anchor_source": "TEXT",
    "computed_activity_count": "INTEGER NOT NULL DEFAULT 0",
    "blocked_activity_count": "INTEGER NOT NULL DEFAULT 0",
}

V84_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_cpm_activity_results (
        cpm_run_id TEXT NOT NULL,
        schedule_version_key TEXT NOT NULL,
        project_key TEXT NOT NULL,
        activity_id TEXT NOT NULL,
        activity_name TEXT,
        topological_index INTEGER,
        computed_early_start TEXT,
        computed_early_finish TEXT,
        early_start_offset_days REAL,
        early_finish_offset_days REAL,
        duration_value REAL,
        duration_unit TEXT,
        duration_source TEXT,
        predecessor_count INTEGER NOT NULL DEFAULT 0,
        successor_count INTEGER NOT NULL DEFAULT 0,
        forward_pass_status TEXT NOT NULL,
        forward_pass_notes_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (cpm_run_id, activity_id),
        FOREIGN KEY (cpm_run_id) REFERENCES schedule_cpm_runs(cpm_run_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_activity_results_version "
    "ON schedule_cpm_activity_results(schedule_version_key)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_activity_results_run "
    "ON schedule_cpm_activity_results(cpm_run_id)",
    """
    CREATE TABLE IF NOT EXISTS schedule_cpm_relationship_results (
        cpm_run_id TEXT NOT NULL,
        schedule_version_key TEXT NOT NULL,
        project_key TEXT NOT NULL,
        relationship_row_id INTEGER,
        relationship_ref TEXT,
        predecessor_activity_id TEXT NOT NULL,
        successor_activity_id TEXT NOT NULL,
        relationship_type TEXT,
        lag_value TEXT,
        lag_unit TEXT,
        normalized_lag_days REAL,
        predecessor_early_start_offset REAL,
        predecessor_early_finish_offset REAL,
        candidate_successor_early_start_offset REAL,
        relationship_calc_status TEXT NOT NULL,
        relationship_calc_notes_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cpm_run_id) REFERENCES schedule_cpm_runs(cpm_run_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_relationship_results_run "
    "ON schedule_cpm_relationship_results(cpm_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_cpm_relationship_results_version "
    "ON schedule_cpm_relationship_results(schedule_version_key)",
]
