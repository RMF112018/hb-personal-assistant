"""V117 — NAS Source-Index bootstrap readiness + reconciliation receipts.

Two additive tables that give the source-index watcher an explicit, durable notion of *readiness*
and a receipt trail for its safety-net reconciliation scans. Neither table duplicates existing
infrastructure: the file-event/file-index queue stays ``source_intelligence_events``, watcher
heartbeat/lease/root k/v state stays ``source_intelligence_state``, and structure ingest run metadata
stays ``source_structure_runs``.

``source_index_bootstrap_state`` — one row per *file-index* source root (``root_key`` == the
``ExternalSourceRoot.source_root_key``). It records whether each of the two index layers (file/content
and folder/structure) has been bootstrapped and whether the root is therefore safe for the watcher to
enter steady-state operation. ``watcher_ready`` is set true only when the required baseline layers are
present (see ``source_bootstrap``). No absolute host paths — ``root_key`` is opaque/root-relative.

``source_index_reconciliation_runs`` — one row per lightweight/full reconciliation scan that walks a
root to catch events the watcher may have missed. Records counts (files/folders seen, changes detected,
events enqueued, errors) and timestamps. Reconciliation only *flags* structure drift; it does not
rebuild the structure index (the directory-event -> structure-rebuild bridge is deferred).

Additive only; both tables ship EMPTY. Rows are written exclusively by out-of-band CLI/operator jobs
(``hb-assistant source-watch bootstrap`` / ``reconcile``), never from a request handler.
"""

from __future__ import annotations

V117_TABLES: tuple[str, ...] = (
    "source_index_bootstrap_state",
    "source_index_reconciliation_runs",
)

RECONCILE_SCAN_TYPE_VALUES: tuple[str, ...] = ("lightweight", "full")


V117_SOURCE_INDEX_BOOTSTRAP_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS source_index_bootstrap_state (
      root_key TEXT PRIMARY KEY,
      file_index_bootstrapped INTEGER NOT NULL DEFAULT 0 CHECK(file_index_bootstrapped IN (0,1)),
      file_index_last_bootstrap_at TEXT,
      file_index_last_success_at TEXT,
      file_index_status TEXT,
      structure_index_bootstrapped INTEGER NOT NULL DEFAULT 0
        CHECK(structure_index_bootstrapped IN (0,1)),
      structure_index_last_bootstrap_at TEXT,
      structure_index_last_success_at TEXT,
      structure_index_status TEXT,
      watcher_ready INTEGER NOT NULL DEFAULT 0 CHECK(watcher_ready IN (0,1)),
      last_health_check_at TEXT,
      last_error TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_index_bootstrap_state_ready "
    "ON source_index_bootstrap_state(watcher_ready)",
    f"""
    CREATE TABLE IF NOT EXISTS source_index_reconciliation_runs (
      run_id TEXT PRIMARY KEY,
      root_key TEXT NOT NULL,
      started_at TEXT,
      finished_at TEXT,
      status TEXT NOT NULL DEFAULT 'running'
        CHECK(status IN ('running','completed','failed')),
      scan_type TEXT NOT NULL
        CHECK(scan_type IN ({",".join(f"'{v}'" for v in RECONCILE_SCAN_TYPE_VALUES)})),
      files_seen INTEGER NOT NULL DEFAULT 0,
      folders_seen INTEGER NOT NULL DEFAULT 0,
      changes_detected INTEGER NOT NULL DEFAULT 0,
      events_enqueued INTEGER NOT NULL DEFAULT 0,
      errors_count INTEGER NOT NULL DEFAULT 0,
      last_error TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_index_reconciliation_runs_root "
    "ON source_index_reconciliation_runs(root_key, created_at)",
]
