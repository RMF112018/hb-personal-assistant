"""V118 — NAS Source-Index bootstrap RUN records (durable progress + lifecycle).

One additive table, ``source_index_bootstrap_runs``, giving initial/rebuild/reconcile/poll scans the
same first-class, durable run trail that reconciliation already has (``source_index_reconciliation_runs``,
V117) but the initial file-index bootstrap lacked. A run row is created when a scan starts, heartbeated
throttled during the walk, and closed to a terminal status when it ends — so an operator can see live
progress and a crash (SIGKILL/OOM) leaves a diagnosable ``running`` row instead of nothing.

Statuses:

* ``running``      — active; ``heartbeat_at`` advances while alive.
* ``completed``    — walk finished (delete-reconcile ran).
* ``partial``      — a per-pass budget stopped the walk early; a resume is needed (NOT an error).
* ``failed``       — the scan raised; ``last_error_code`` carries a bounded reason.
* ``interrupted``  — the process exited without closing the run (``finally`` backstop).
* ``abandoned``    — a prior ``running`` row whose heartbeat went stale (SIGKILL/OOM) reaped at next start.
* ``superseded``   — retained history: a later run resumed this root; linkage via
  ``superseded_by_run_id`` / ``resumed_from_run_id`` (a prior ``partial`` is NEVER overwritten).

Concurrency: a partial UNIQUE index on ``root_key`` WHERE ``status='running'`` makes "one active run per
root" an atomic DB invariant — a second concurrent start hits the unique constraint (callers treat the
conflict as retryable, not fatal). No absolute host paths — ``root_key`` is opaque and
``current_rel_prefix`` is a redacted parent-hash+depth token.

Additive only; ships EMPTY. Rows are written exclusively by the scan orchestration wrapper, never from a
request handler.
"""

from __future__ import annotations

V118_TABLES: tuple[str, ...] = ("source_index_bootstrap_runs",)

BOOTSTRAP_RUN_STATUS_VALUES: tuple[str, ...] = (
    "running",
    "partial",
    "completed",
    "failed",
    "interrupted",
    "abandoned",
    "superseded",
)

BOOTSTRAP_RUN_MODE_VALUES: tuple[str, ...] = ("bootstrap", "rebuild", "reconcile", "poll")


V118_SOURCE_INDEX_BOOTSTRAP_RUNS_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS source_index_bootstrap_runs (
      run_id TEXT PRIMARY KEY,
      root_key TEXT NOT NULL,
      mode TEXT NOT NULL DEFAULT 'bootstrap'
        CHECK(mode IN ({",".join(f"'{v}'" for v in BOOTSTRAP_RUN_MODE_VALUES)})),
      phase TEXT,
      status TEXT NOT NULL DEFAULT 'running'
        CHECK(status IN ({",".join(f"'{v}'" for v in BOOTSTRAP_RUN_STATUS_VALUES)})),
      started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      heartbeat_at TEXT,
      finished_at TEXT,
      files_walked INTEGER NOT NULL DEFAULT 0,
      metadata_upserted INTEGER NOT NULL DEFAULT 0,
      files_unchanged INTEGER NOT NULL DEFAULT 0,
      content_attempted INTEGER NOT NULL DEFAULT 0,
      content_succeeded INTEGER NOT NULL DEFAULT 0,
      content_failed INTEGER NOT NULL DEFAULT 0,
      errors_count INTEGER NOT NULL DEFAULT 0,
      current_rel_prefix TEXT,
      bounded_reason TEXT,
      last_error_code TEXT,
      stop_requested INTEGER NOT NULL DEFAULT 0 CHECK(stop_requested IN (0,1)),
      completed_metadata_walk INTEGER NOT NULL DEFAULT 0
        CHECK(completed_metadata_walk IN (0,1)),
      reconciliation_completed INTEGER NOT NULL DEFAULT 0
        CHECK(reconciliation_completed IN (0,1)),
      resumed_from_run_id TEXT,
      superseded_by_run_id TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Atomic "one active run per root": a second concurrent start collides on this partial unique index.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_source_index_bootstrap_runs_active "
    "ON source_index_bootstrap_runs(root_key) WHERE status='running'",
    "CREATE INDEX IF NOT EXISTS idx_source_index_bootstrap_runs_root "
    "ON source_index_bootstrap_runs(root_key, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_source_index_bootstrap_runs_status "
    "ON source_index_bootstrap_runs(status, heartbeat_at)",
]
