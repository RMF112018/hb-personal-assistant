"""V76 canonical schedule identity foundation tables.

Additive schedule identity tables for linking committed uploaded schedule
versions without changing the existing schedule_version_key contract.
"""

from __future__ import annotations

V76_TABLES: tuple[str, ...] = (
    "schedule_identities",
    "schedule_version_identity_matches",
)

V76_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schedule_identities (
      schedule_identity_key TEXT PRIMARY KEY,
      project_key TEXT NOT NULL,
      identity_status TEXT NOT NULL DEFAULT 'active',
      canonical_schedule_name TEXT,
      normalized_source_project_id TEXT,
      normalized_source_project_name TEXT,
      source_system TEXT,
      source_format TEXT,
      representative_activity_id_set_fingerprint TEXT,
      representative_wbs_fingerprint TEXT,
      representative_relationship_graph_fingerprint TEXT,
      first_import_id TEXT,
      first_schedule_version_key TEXT,
      latest_import_id TEXT,
      latest_schedule_version_key TEXT,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_identities_project
    ON schedule_identities(project_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_identities_latest_version
    ON schedule_identities(latest_schedule_version_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_identities_source_project
    ON schedule_identities(
      project_key, normalized_source_project_id, normalized_source_project_name
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule_version_identity_matches (
      match_id TEXT PRIMARY KEY,
      schedule_identity_key TEXT NOT NULL,
      schedule_version_key TEXT NOT NULL,
      import_id TEXT NOT NULL,
      project_key TEXT NOT NULL,
      source_system TEXT,
      source_format TEXT,
      source_filename_redacted TEXT,
      normalized_source_project_id TEXT,
      normalized_source_project_name TEXT,
      activity_id_set_fingerprint TEXT,
      wbs_fingerprint TEXT,
      relationship_graph_fingerprint TEXT,
      activity_count INTEGER NOT NULL DEFAULT 0,
      relationship_count INTEGER NOT NULL DEFAULT 0,
      wbs_count INTEGER NOT NULL DEFAULT 0,
      match_type TEXT NOT NULL,
      match_status TEXT NOT NULL DEFAULT 'resolved',
      match_rule TEXT,
      confidence_score TEXT,
      requires_review INTEGER NOT NULL DEFAULT 0,
      no_match_reason TEXT,
      candidate_count INTEGER NOT NULL DEFAULT 0,
      matched_existing_identity_key TEXT,
      matched_prior_schedule_version_key TEXT,
      winning_candidate_schedule_version_key TEXT,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (schedule_identity_key) REFERENCES schedule_identities(schedule_identity_key)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_version_identity_matches_identity
    ON schedule_version_identity_matches(schedule_identity_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_version_identity_matches_version
    ON schedule_version_identity_matches(schedule_version_key);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_version_identity_matches_import
    ON schedule_version_identity_matches(import_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_schedule_version_identity_matches_project
    ON schedule_version_identity_matches(project_key);
    """,
]
