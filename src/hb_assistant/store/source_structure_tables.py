"""V115 — NAS Source-Structure Layered Index.

A layered, deterministic, reviewable map of the NAS source folders so connected LLM clients can
navigate hundreds of thousands of folders/files across multiple roots: which root is authoritative,
which folders are backups/noise/generated output, where a project's files live, and where to search
first. Populated OUTSIDE the MCP request path (CLI/scheduled jobs parse a printed folder-tree
artifact or perform a bounded metadata scan); MCP/API handlers only read these precomputed rows.

Additive only. All tables ship EMPTY. No source-file bodies, no absolute host paths, no raw SQL are
stored here — rows carry root-relative ``rel_path`` + opaque ``folder_id`` refs. Ollama enrichment is
a later increment; ``classification_source``/``summary_kind`` keep ``ollama`` as an allowed value for
forward-compat, but no model-derived rows are written by this schema version.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# --- Root-level enums -------------------------------------------------------------------------
ROOT_CLASS_VALUES: tuple[str, ...] = (
    "work",
    "construction_work",
    "personal",
    "backup_mirror",
    "generated_output",
    "vault",
    "unknown",
)

TRUST_TIER_VALUES: tuple[str, ...] = (
    "high",
    "medium",
    "low",
    "generated",
    "supplemental",
)

INDEX_POLICY_VALUES: tuple[str, ...] = (
    "deep_metadata",
    "selective_metadata",
    "shallow_map",
    "generated_outputs_only",
    "vault_notes_only",
)

# --- Folder-level enums -----------------------------------------------------------------------
FOLDER_CLASS_VALUES: tuple[str, ...] = (
    "project_root",
    "construction_docs",
    "financials",
    "drawings",
    "rfis",
    "submittals",
    "contracts",
    "change_orders",
    "closeout",
    "photos",
    "generated_output",
    "backup_mirror",
    "noise",
    "dev_runtime",
    "personal",
    "unknown",
)

DOC_FAMILY_VALUES: tuple[str, ...] = (
    "rfi",
    "submittal",
    "drawings",
    "specifications",
    "pay_app",
    "change_order",
    "contract",
    "schedule",
    "daily_log",
    "photos",
    "closeout",
    "estimate",
    "bid",
    "safety",
    "unknown",
)

CLASSIFICATION_SOURCE_VALUES: tuple[str, ...] = (
    "rule",
    "ollama",  # forward-compat; no rows written with this value in V115
    "manual_override",
    "inherited",
    "unknown",
)

# --- Entity enums -----------------------------------------------------------------------------
ENTITY_TYPE_VALUES: tuple[str, ...] = (
    "project",
    "company",
    "person",
    "property",
    "unknown",
)

RELATIONSHIP_TYPE_VALUES: tuple[str, ...] = (
    "primary_project_folder",
    "supporting_folder",
    "archive_folder",
    "backup_folder",
    "generated_output_folder",
    "candidate",
)

# --- Summary / hint / finding / run enums -----------------------------------------------------
SUMMARY_SUBJECT_TYPE_VALUES: tuple[str, ...] = ("root", "folder", "project")

SUMMARY_KIND_VALUES: tuple[str, ...] = (
    "deterministic",
    "ollama",  # forward-compat; no rows written with this value in V115
    "manual",
)

HINT_TYPE_VALUES: tuple[str, ...] = (
    "search_route",
    "avoid_root",
    "prefer_root",
    "project_lookup",
    "doc_family_lookup",
)

FINDING_SEVERITY_VALUES: tuple[str, ...] = ("info", "warning", "error")

FINDING_STATUS_VALUES: tuple[str, ...] = ("open", "acknowledged", "resolved", "ignored")

RUN_TYPE_VALUES: tuple[str, ...] = (
    "ingest_tree",
    "scan_roots",
    "classify",
    "summarize",
    "quality",
    "evidence_export",
)

RUN_STATUS_VALUES: tuple[str, ...] = ("running", "completed", "failed", "aborted")


V115_TABLES: tuple[str, ...] = (
    "source_structure_roots",
    "source_structure_folders",
    "source_structure_entities",
    "source_structure_entity_folders",
    "source_structure_summaries",
    "source_structure_hints",
    "source_structure_findings",
    "source_structure_runs",
)


V115_SOURCE_STRUCTURE_STATEMENTS: list[str] = [
    # --- roots ---------------------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_roots (
      root_key TEXT PRIMARY KEY,
      display_name TEXT NOT NULL,
      root_class TEXT NOT NULL CHECK(root_class IN ({_csv(ROOT_CLASS_VALUES)})),
      trust_tier TEXT NOT NULL CHECK(trust_tier IN ({_csv(TRUST_TIER_VALUES)})),
      index_policy TEXT NOT NULL CHECK(index_policy IN ({_csv(INDEX_POLICY_VALUES)})),
      default_search_rank INTEGER NOT NULL,
      is_sensitive INTEGER NOT NULL DEFAULT 0 CHECK(is_sensitive IN (0,1)),
      is_generated_output INTEGER NOT NULL DEFAULT 0 CHECK(is_generated_output IN (0,1)),
      is_backup_mirror INTEGER NOT NULL DEFAULT 0 CHECK(is_backup_mirror IN (0,1)),
      is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
      last_seen_at TEXT,
      last_indexed_at TEXT,
      folder_count INTEGER NOT NULL DEFAULT 0,
      file_count INTEGER NOT NULL DEFAULT 0,
      noise_count INTEGER NOT NULL DEFAULT 0,
      max_depth INTEGER,
      notes TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_roots_rank "
    "ON source_structure_roots(default_search_rank, root_class)",
    # --- folders -------------------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_folders (
      folder_id TEXT PRIMARY KEY,
      root_key TEXT NOT NULL,
      parent_folder_id TEXT,
      rel_path TEXT NOT NULL,
      name TEXT NOT NULL,
      depth INTEGER NOT NULL,
      folder_class TEXT NOT NULL CHECK(folder_class IN ({_csv(FOLDER_CLASS_VALUES)})),
      doc_family TEXT CHECK(doc_family IS NULL OR doc_family IN ({_csv(DOC_FAMILY_VALUES)})),
      trust_tier TEXT NOT NULL CHECK(trust_tier IN ({_csv(TRUST_TIER_VALUES)})),
      search_rank INTEGER NOT NULL,
      is_noise INTEGER NOT NULL DEFAULT 0 CHECK(is_noise IN (0,1)),
      is_backup_mirror INTEGER NOT NULL DEFAULT 0 CHECK(is_backup_mirror IN (0,1)),
      is_generated_output INTEGER NOT NULL DEFAULT 0 CHECK(is_generated_output IN (0,1)),
      is_sensitive INTEGER NOT NULL DEFAULT 0 CHECK(is_sensitive IN (0,1)),
      is_project_candidate INTEGER NOT NULL DEFAULT 0 CHECK(is_project_candidate IN (0,1)),
      project_number TEXT,
      project_name_hint TEXT,
      child_folder_count INTEGER NOT NULL DEFAULT 0,
      file_count INTEGER NOT NULL DEFAULT 0,
      dominant_extensions_json TEXT,
      sample_names_json TEXT,
      fingerprint TEXT,
      last_seen_at TEXT,
      last_indexed_at TEXT,
      classification_source TEXT NOT NULL DEFAULT 'rule'
        CHECK(classification_source IN ({_csv(CLASSIFICATION_SOURCE_VALUES)})),
      classification_confidence REAL NOT NULL DEFAULT 0.0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(root_key, rel_path)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_folders_root_depth "
    "ON source_structure_folders(root_key, depth)",
    "CREATE INDEX IF NOT EXISTS idx_source_structure_folders_parent "
    "ON source_structure_folders(parent_folder_id)",
    "CREATE INDEX IF NOT EXISTS idx_source_structure_folders_class "
    "ON source_structure_folders(folder_class)",
    "CREATE INDEX IF NOT EXISTS idx_source_structure_folders_doc_family "
    "ON source_structure_folders(doc_family)",
    "CREATE INDEX IF NOT EXISTS idx_source_structure_folders_project "
    "ON source_structure_folders(project_number)",
    "CREATE INDEX IF NOT EXISTS idx_source_structure_folders_rank "
    "ON source_structure_folders(root_key, search_rank)",
    "CREATE INDEX IF NOT EXISTS idx_source_structure_folders_flags "
    "ON source_structure_folders(is_noise, is_backup_mirror, is_generated_output)",
    # --- entities ------------------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_entities (
      entity_id TEXT PRIMARY KEY,
      entity_type TEXT NOT NULL CHECK(entity_type IN ({_csv(ENTITY_TYPE_VALUES)})),
      canonical_key TEXT NOT NULL,
      display_name TEXT,
      project_number TEXT,
      project_name TEXT,
      confidence REAL NOT NULL DEFAULT 0.0,
      first_seen_at TEXT,
      last_seen_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(entity_type, canonical_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_entities_project "
    "ON source_structure_entities(project_number)",
    # --- entity ↔ folder ----------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_entity_folders (
      entity_id TEXT NOT NULL,
      folder_id TEXT NOT NULL,
      relationship_type TEXT NOT NULL CHECK(relationship_type IN ({_csv(RELATIONSHIP_TYPE_VALUES)})),
      confidence REAL NOT NULL DEFAULT 0.0,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(entity_id, folder_id, relationship_type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_entity_folders_folder "
    "ON source_structure_entity_folders(folder_id)",
    # --- summaries -----------------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_summaries (
      summary_id TEXT PRIMARY KEY,
      subject_type TEXT NOT NULL CHECK(subject_type IN ({_csv(SUMMARY_SUBJECT_TYPE_VALUES)})),
      subject_id TEXT NOT NULL,
      summary_text TEXT NOT NULL,
      summary_kind TEXT NOT NULL CHECK(summary_kind IN ({_csv(SUMMARY_KIND_VALUES)})),
      model_name TEXT,
      prompt_version TEXT,
      input_fingerprint TEXT,
      confidence REAL NOT NULL DEFAULT 0.0,
      source_metadata_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(subject_type, subject_id, summary_kind)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_summaries_subject "
    "ON source_structure_summaries(subject_type, subject_id)",
    # --- routing hints -------------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_hints (
      hint_id TEXT PRIMARY KEY,
      hint_type TEXT NOT NULL CHECK(hint_type IN ({_csv(HINT_TYPE_VALUES)})),
      query_family TEXT,
      root_key TEXT,
      folder_id TEXT,
      entity_id TEXT,
      rank INTEGER NOT NULL,
      hint_text TEXT NOT NULL,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_hints_family "
    "ON source_structure_hints(query_family, rank)",
    # --- quality findings ----------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_findings (
      finding_id TEXT PRIMARY KEY,
      finding_type TEXT NOT NULL,
      severity TEXT NOT NULL CHECK(severity IN ({_csv(FINDING_SEVERITY_VALUES)})),
      root_key TEXT,
      folder_id TEXT,
      entity_id TEXT,
      title TEXT NOT NULL,
      details TEXT,
      evidence_json TEXT,
      status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ({_csv(FINDING_STATUS_VALUES)})),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_findings_lookup "
    "ON source_structure_findings(status, severity, finding_type)",
    # --- runs ----------------------------------------------------------------------------------
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_runs (
      run_id TEXT PRIMARY KEY,
      run_type TEXT NOT NULL CHECK(run_type IN ({_csv(RUN_TYPE_VALUES)})),
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL CHECK(status IN ({_csv(RUN_STATUS_VALUES)})),
      roots_json TEXT,
      options_json TEXT,
      counts_json TEXT,
      error_text TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_runs_type "
    "ON source_structure_runs(run_type, started_at)",
]
