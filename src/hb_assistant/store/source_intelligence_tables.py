"""V93 Source Intelligence Index tables.

Durable index over EXTERNAL source files (and links to existing domain rows) so the
Obsidian MCP can search broadly without live full-vault scans. Obsidian stays the
curated knowledge layer; raw files are never copied into the vault.

Invariants encoded as DDL CHECK constraints (mirroring ``email_messages.full_body_persisted``):
  * ``source_intelligence_text``/``_chunks`` may never persist a raw body
    (``raw_body_persisted = 0``) and are always redaction-applied (``redaction_applied = 1``).
  * Every source row is either a real file (``rel_path``) OR a link to an existing domain
    row (``domain_ref_table`` + ``domain_ref_id``) — never neither (table-level CHECK).
  * Email sources are LINK-ONLY: the indexer never writes ``_text``/``_chunks`` for them
    (no raw email body ever leaves the encrypted Text Vault).

FTS5 strategy: two REGULAR (non-contentless) FTS5 tables holding only bounded, already
non-sensitive fields (excerpt/rel_path/project_key/tags). The repository owns sync explicitly
(no triggers): rowid is SQLite-assigned on insert and stored back in
``source_intelligence_metadata.fts_rowid`` so reindex/delete is a plain ``DELETE ... WHERE rowid=?``.
The two FTS tables are created only when the runtime SQLite has FTS5 (probed in the migrator);
``source_intelligence_state['fts_available']`` records the outcome.
"""

from __future__ import annotations

import sqlite3

# --- CHECK value vocabularies (exported for tests + repo code) --------------------------------
SOURCE_KIND_VALUES: tuple[str, ...] = (
    "external_file",
    "obsidian_note",
    "email",
    "procore",
    "schedule",
)
EXTRACTION_STATUS_VALUES: tuple[str, ...] = (
    "pending",
    "ok",
    "unsupported",
    "failed",
    "skipped_too_large",
)
RELATION_DST_KIND_VALUES: tuple[str, ...] = (
    "project",
    "source",
    "obsidian_note",
    "email",
    "procore",
    "schedule",
)
RELATION_VALUES: tuple[str, ...] = (
    "belongs_to_project",
    "mentions",
    "derived_from",
    "links_to",
)
GENERATION_STATUS_VALUES: tuple[str, ...] = ("not_generated", "generated", "stale")
EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "modified",
    "deleted",
    "reindex_requested",
    "rebuild",
)
EVENT_STATUS_VALUES: tuple[str, ...] = ("queued", "processing", "done", "error", "skipped")

V93_TABLES: tuple[str, ...] = (
    "source_intelligence_sources",
    "source_intelligence_metadata",
    "source_intelligence_text",
    "source_intelligence_chunks",
    "source_intelligence_relationships",
    "source_intelligence_generated_notes",
    "source_intelligence_events",
    "source_intelligence_state",
)

V93_FTS_TABLES: tuple[str, ...] = (
    "source_intelligence_fts",
    "obsidian_note_fts",
)


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


V93_STATEMENTS: list[str] = [
    # 1. sources — one row per indexed source (file OR domain link)
    f"""
    CREATE TABLE IF NOT EXISTS source_intelligence_sources (
      source_id TEXT PRIMARY KEY,
      source_kind TEXT NOT NULL CHECK(source_kind IN ({_csv(SOURCE_KIND_VALUES)})),
      source_root_key TEXT,
      rel_path TEXT,
      abs_path_hash TEXT,
      domain_ref_table TEXT,
      domain_ref_id TEXT,
      project_key TEXT,
      project_number TEXT,
      active INTEGER NOT NULL DEFAULT 1,
      deleted INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CHECK (
        (rel_path IS NOT NULL)
        OR (domain_ref_table IS NOT NULL AND domain_ref_id IS NOT NULL)
      )
    );
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_si_sources_relpath "
    "ON source_intelligence_sources(source_kind, rel_path) WHERE rel_path IS NOT NULL;",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_si_sources_domain "
    "ON source_intelligence_sources(domain_ref_table, domain_ref_id) WHERE domain_ref_id IS NOT NULL;",
    "CREATE INDEX IF NOT EXISTS idx_si_sources_project ON source_intelligence_sources(project_key);",
    "CREATE INDEX IF NOT EXISTS idx_si_sources_active ON source_intelligence_sources(active, deleted);",
    "CREATE INDEX IF NOT EXISTS idx_si_sources_root ON source_intelligence_sources(source_root_key);",
    # 2. metadata — stat + extraction status + fts rowid map (idempotency keys live here)
    f"""
    CREATE TABLE IF NOT EXISTS source_intelligence_metadata (
      source_id TEXT PRIMARY KEY REFERENCES source_intelligence_sources(source_id),
      file_ext TEXT,
      size_bytes INTEGER,
      mtime_ns INTEGER,
      content_sha256 TEXT,
      page_count INTEGER,
      paragraph_count INTEGER,
      sheet_count INTEGER,
      extraction_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(extraction_status IN ({_csv(EXTRACTION_STATUS_VALUES)})),
      extraction_failure_code TEXT,
      fts_rowid INTEGER,
      indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_si_metadata_sha ON source_intelligence_metadata(content_sha256);",
    # 3. text — bounded excerpt + sha + optional Text Vault ref. NEVER a raw body.
    """
    CREATE TABLE IF NOT EXISTS source_intelligence_text (
      source_id TEXT PRIMARY KEY REFERENCES source_intelligence_sources(source_id),
      text_excerpt TEXT,
      excerpt_char_count INTEGER NOT NULL DEFAULT 0 CHECK(excerpt_char_count >= 0),
      excerpt_truncated INTEGER NOT NULL DEFAULT 0,
      full_text_sha256 TEXT,
      text_vault_ref TEXT,
      raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
      redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1),
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # 4. chunks — bounded per-source retrieval chunks (capped count/size by the indexer)
    """
    CREATE TABLE IF NOT EXISTS source_intelligence_chunks (
      chunk_id TEXT PRIMARY KEY,
      source_id TEXT NOT NULL REFERENCES source_intelligence_sources(source_id),
      ordinal INTEGER NOT NULL,
      chunk_text TEXT NOT NULL,
      char_count INTEGER NOT NULL,
      raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(source_id, ordinal)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_si_chunks_source ON source_intelligence_chunks(source_id);",
    # 5. relationships — file<->project, file<->note, link graph foundation
    f"""
    CREATE TABLE IF NOT EXISTS source_intelligence_relationships (
      relationship_id TEXT PRIMARY KEY,
      src_source_id TEXT NOT NULL REFERENCES source_intelligence_sources(source_id),
      dst_kind TEXT NOT NULL CHECK(dst_kind IN ({_csv(RELATION_DST_KIND_VALUES)})),
      dst_ref TEXT NOT NULL,
      relation TEXT NOT NULL CHECK(relation IN ({_csv(RELATION_VALUES)})),
      confidence TEXT,
      evidence_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(src_source_id, dst_kind, dst_ref, relation)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_si_rel_src ON source_intelligence_relationships(src_source_id);",
    "CREATE INDEX IF NOT EXISTS idx_si_rel_dst ON source_intelligence_relationships(dst_kind, dst_ref);",
    # 6. generated_notes — STUB this slice (status transitions only; generation is a later slice)
    f"""
    CREATE TABLE IF NOT EXISTS source_intelligence_generated_notes (
      generated_note_id TEXT PRIMARY KEY,
      source_id TEXT NOT NULL REFERENCES source_intelligence_sources(source_id),
      note_rel_path TEXT,
      generation_status TEXT NOT NULL DEFAULT 'not_generated'
        CHECK(generation_status IN ({_csv(GENERATION_STATUS_VALUES)})),
      generated_at TEXT,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(source_id, note_rel_path)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_si_gennotes_source ON source_intelligence_generated_notes(source_id);",
    "CREATE INDEX IF NOT EXISTS idx_si_gennotes_status "
    "ON source_intelligence_generated_notes(generation_status);",
    # 7. events — durable indexer queue + audit (no content, bounded error codes)
    f"""
    CREATE TABLE IF NOT EXISTS source_intelligence_events (
      event_id TEXT PRIMARY KEY,
      source_id TEXT,
      rel_path TEXT,
      source_root_key TEXT,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(EVENT_TYPE_VALUES)})),
      status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ({_csv(EVENT_STATUS_VALUES)})),
      error_code TEXT,
      attempts INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_si_events_status ON source_intelligence_events(status, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_si_events_source ON source_intelligence_events(source_id);",
    # 8. state — singleton key/value (fts_available, last_full_scan, fts_rowid counter, roots hash)
    """
    CREATE TABLE IF NOT EXISTS source_intelligence_state (
      state_key TEXT PRIMARY KEY,
      state_value TEXT,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
]

# Created only when FTS5 is available (probed by the migrator). Regular FTS5 tables: the
# repository assigns/stores rowid and keeps these in sync explicitly. Only bounded,
# non-sensitive fields are indexed here.
# Both FTS tables share identical columns so the repository has one insert/delete path.
# ``aux`` carries project_key for external files and tags for obsidian notes (FTS MATCH
# searches all columns; column-scoped filters use ``aux``/``rel_path`` explicitly).
V93_FTS_STATEMENTS: list[str] = [
    "CREATE VIRTUAL TABLE IF NOT EXISTS source_intelligence_fts "
    "USING fts5(text_excerpt, rel_path, aux, tokenize='unicode61');",
    "CREATE VIRTUAL TABLE IF NOT EXISTS obsidian_note_fts "
    "USING fts5(text_excerpt, rel_path, aux, tokenize='unicode61');",
]


def fts5_available(conn: sqlite3.Connection) -> bool:
    """True when the runtime SQLite can create FTS5 virtual tables."""
    try:
        row = conn.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')").fetchone()
        if row is not None and int(row[0]) == 1:
            return True
    except sqlite3.Error:
        pass
    # Fallback probe: try to create a throwaway temp FTS5 table.
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.__si_fts_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS temp.__si_fts_probe")
        return True
    except sqlite3.Error:
        return False
