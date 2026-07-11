"""V122 — NAS Source-Index metadata-first SCAN GENERATIONS + generation-aware source/metadata state.

PR 1 (V119) made bounded scans *safe* but each bounded pass still re-walks the root from the top and
relies on a per-file stat fast-skip; there is no durable traversal position, so a very large root can
spend an entire pass re-stat'ing the already-indexed prefix and never make forward progress. PR 2 adds
a durable **scan generation** that spans many V119 passes, carries a persisted traversal cursor, and
reconciles deletions *by generation* (not by an in-memory ``seen`` set) only after a complete metadata
walk.

This module ships the additive V122 DDL:

* ``source_index_scan_generations`` — one durable generation per root lifecycle. A generation owns the
  traversal cursor (``cursor_json``), an ownership lease (``active_run_id`` + ``owner_heartbeat_at`` — a
  stale lease is *released* back to ``partial``/``reconcile_pending`` with the cursor preserved, never
  discarded), a reconciliation checkpoint (``reconcile_cursor_json``), and a ``policy_fingerprint`` that
  invalidates the generation on any metadata/search-affecting policy or code change.
* Additive columns on the V93 ``source_intelligence_sources`` (``last_seen_generation`` / ``last_seen_at``
  — a pure last-seen stamp must NOT perturb the material ``updated_at`` — and ``last_indexed_fingerprint``,
  the policy fingerprint under which the row was last indexed, so a fast-skip is allowed only when the row
  is current for CURRENT policy: any fingerprint change — sensitivity, project matcher, FTS format, root
  path, exclusions — forces the row to be reprocessed rather than skipped) and ``source_intelligence_metadata``
  (``extraction_disposition`` / ``content_indexed_at``). Added **nullable with no row-wide UPDATE**: NULL is
  interpreted through a legacy-status compatibility mapping at read time and the real value fills
  incrementally as each row is next observed in a bounded metadata generation.
* One additive column on the V119 ``source_index_bootstrap_runs`` (``generation_id``) linking each bounded
  pass to its longer-lived generation.

Statuses (``SCAN_GENERATION_STATUS_VALUES``):

* ``running``           — a pass currently owns the generation (``active_run_id`` set, heartbeat alive).
* ``partial``           — a per-pass bound stopped the metadata walk early; resumable from ``cursor_json``.
* ``reconcile_pending`` — the metadata walk completed but deletion reconciliation has not finished;
  resumable from ``reconcile_cursor_json`` WITHOUT re-walking the tree.
* ``completed``         — metadata walk + deletion reconciliation both finished.
* ``failed``            — a no-forward-progress condition (high-fanout ``directory_fanout_limit`` or a
  per-generation hard ceiling) or an unrecoverable error; performs NO reconciliation and requires a
  config/fingerprint change or explicit restart (never silently reopened as ``partial``).
* ``abandoned``         — an invalid/unvalidatable cursor/fingerprint/root state; NO reconciliation,
  restart from root.

Concurrency: a partial UNIQUE index on ``root_key`` WHERE status is one of the three *active* states makes
"one active generation per root" an atomic DB invariant. No absolute host paths — ``root_key`` is opaque
and ``root_path_hash`` is a hash, never the path itself.

Additive only; ships EMPTY (generation rows) / column-additive (existing tables). Written exclusively by
``SourceIndexScanGenerationsRepository`` via the scan orchestration wrapper.
"""

from __future__ import annotations

V122_TABLES: tuple[str, ...] = ("source_index_scan_generations",)

SCAN_GENERATION_STATUS_VALUES: tuple[str, ...] = (
    "running",
    "partial",
    "reconcile_pending",
    "completed",
    "failed",
    "abandoned",
)

# The three states in which a generation is "active" (holds resumable progress and may own a lease).
SCAN_GENERATION_ACTIVE_STATUSES: tuple[str, ...] = ("running", "partial", "reconcile_pending")

# Explicit metadata/content disposition, distinct from the extraction_status CHECK vocabulary. Resolves
# the PR 1 ambiguity where ``pending`` meant both "content eligible, not yet extracted" and "intentionally
# metadata-only". NULL on a legacy row is mapped from extraction_status at read time.
EXTRACTION_DISPOSITION_VALUES: tuple[str, ...] = (
    "content",
    "metadata_only",
    "unsupported",
    "too_large",
)


V122_SOURCE_INDEX_SCAN_GENERATIONS_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS source_index_scan_generations (
      generation_id TEXT PRIMARY KEY,
      root_key TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'running'
        CHECK(status IN ({",".join(f"'{v}'" for v in SCAN_GENERATION_STATUS_VALUES)})),
      traversal_version INTEGER NOT NULL DEFAULT 1,
      root_path_hash TEXT NOT NULL,
      policy_fingerprint TEXT NOT NULL,
      cursor_json TEXT,
      active_run_id TEXT,
      owner_heartbeat_at TEXT,
      reconcile_cursor_json TEXT,
      reconcile_started_at TEXT,
      started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_walk_completed_at TEXT,
      reconciliation_completed_at TEXT,
      finished_at TEXT,
      files_observed INTEGER NOT NULL DEFAULT 0,
      metadata_upserted INTEGER NOT NULL DEFAULT 0,
      files_unchanged INTEGER NOT NULL DEFAULT 0,
      errors_count INTEGER NOT NULL DEFAULT 0,
      deleted_count INTEGER NOT NULL DEFAULT 0,
      last_error_code TEXT
    )
    """,
    # Atomic "one active generation per root": a second concurrent active generation collides here.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_source_index_scan_generations_active "
    "ON source_index_scan_generations(root_key) "
    "WHERE status IN ('running','partial','reconcile_pending')",
    "CREATE INDEX IF NOT EXISTS idx_source_index_scan_generations_root "
    "ON source_index_scan_generations(root_key, started_at)",
    "CREATE INDEX IF NOT EXISTS idx_source_index_scan_generations_status "
    "ON source_index_scan_generations(status, updated_at)",
    # Reconciliation predicate index: (root, kind, deleted, last_seen_generation). The columns it
    # references are added below via the parity-guarded ADD COLUMN path, so this index is created AFTER.
]

# Additive nullable columns on the V93/V119 tables, applied via a parity-guarded ADD COLUMN (skipped if
# the column already exists) so the migration is idempotent under an unconditional re-run — never a raw
# ALTER that raises "duplicate column". Nullable; NO row-wide backfill (legacy NULL is mapped at read
# time and filled incrementally). ``last_seen_at`` is SEPARATE from ``updated_at`` so a pure last-seen
# stamp never perturbs material change tracking.
V122_ADD_COLUMNS: list[tuple[str, str, str]] = [
    ("source_intelligence_sources", "last_seen_generation", "TEXT"),
    ("source_intelligence_sources", "last_seen_at", "TEXT"),
    # Policy fingerprint the row was last indexed under. A fast-skip is allowed only when this equals the
    # current generation's fingerprint, so ANY metadata/search-affecting policy or code change (sensitivity,
    # project matcher, FTS format, root path, exclusions) forces the row to be reprocessed, not skipped.
    ("source_intelligence_sources", "last_indexed_fingerprint", "TEXT"),
    ("source_intelligence_metadata", "extraction_disposition", "TEXT"),
    ("source_intelligence_metadata", "content_indexed_at", "TEXT"),
    ("source_index_bootstrap_runs", "generation_id", "TEXT"),
]

# Index created only after its referenced columns exist (see the migrator's V122 apply block).
V122_POST_COLUMN_STATEMENTS: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_si_sources_last_seen_gen "
    "ON source_intelligence_sources(source_root_key, source_kind, deleted, last_seen_generation)",
]
