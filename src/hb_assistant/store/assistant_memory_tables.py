"""V103 — Source-Backed Memory Compiler tables (N8C-7).

Compiles the recurring **entities / concepts / domains / projects / people / topics** referenced across
the N8C substrate (sources/cards, claims, enrichment receipts, context packs) into durable, advisory,
source-backed memory objects:
  * ``assistant_memory_nodes`` — canonical objects (deterministic id from normalized identity);
  * ``assistant_memory_mentions`` — source-backed evidence that a node appears somewhere (provenance);
  * ``assistant_memory_compilations`` — bounded summaries for a node (immutable-by-input);
  * ``assistant_memory_events`` — append-only node lifecycle log (NOT a bridge/job event system).

Narrow and neutral — NOT a graph database, NOT a vector store, NOT a bridge/job schema (that is N8D,
which this slice must not touch or duplicate). Additive only; no existing table is touched.

Advisory, never truth: a memory node's ``status`` / a mention's ``review_tier`` / a compilation NEVER
imply a claim was accepted. The compiler only READS claims; candidate claims stay candidate/unreviewed.
``merged`` / ``archived`` node statuses (and their events) are valid enum values reserved for a future
slice — N8C-7 implements no node-merge and no operator-disposition workflow.

Invariants baked into the schema (DB is the backstop; the models validate first with clean errors):
  * a mention is provenance-backed — table CHECK requires at least one anchor
    (source_id / note_rel_path / claim_id / receipt_id / pack_id / pack_item_id);
  * ``node_type`` / node ``status`` / ``mention_type`` / ``review_tier`` / ``compile_type`` /
    compilation ``status`` / ``event_type`` are enum-constrained;
  * counts are non-negative; ``truncated`` is 0/1; confidence is 0..1;
  * text columns store only BOUNDED excerpts (the models cap them before write) — never a raw source
    body, raw email body, or raw prompt/response.

All four tables ship EMPTY; nothing populates them on startup — only an explicit bounded
``memory compile --apply`` command / service call writes rows. No lifespan / scheduler / watcher /
worker path compiles memory.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# Kind of canonical memory object.
MEMORY_NODE_TYPE_VALUES: tuple[str, ...] = (
    "entity",
    "concept",
    "domain",
    "project",
    "person",
    "organization",
    "place",
    "asset",
    "topic",
    "preference_area",
    "risk_area",
    "unknown",
)

# Node lifecycle. `merged`/`archived` are reserved for a future disposition slice (N8C-7 uses only
# active/stale/superseded).
MEMORY_NODE_STATUS_VALUES: tuple[str, ...] = (
    "active",
    "stale",
    "superseded",
    "merged",
    "archived",
)

# How a node was evidenced in a record.
MEMORY_MENTION_TYPE_VALUES: tuple[str, ...] = (
    "claim_subject",
    "claim_object",
    "source_title",
    "context_pack_item",
    "enrichment_summary",
    "backlink_target",
    "manual_seed",
    "unknown",
)

# Advisory provenance-quality / review tier for a mention or node. NOT a claim disposition.
MEMORY_REVIEW_TIER_VALUES: tuple[str, ...] = (
    "trusted_source_backed",
    "needs_operator_review",
    "low_confidence",
    "stale_source",
    "ambiguous_source",
    "candidate_only",
    "conflict_possible",
)

# Kind of bounded summary compiled for a node.
MEMORY_COMPILE_TYPE_VALUES: tuple[str, ...] = (
    "node_summary",
    "domain_summary",
    "project_summary",
    "topic_summary",
    "review_packet",
)

# Compilation lifecycle.
MEMORY_COMPILATION_STATUS_VALUES: tuple[str, ...] = (
    "built",
    "stale",
    "superseded",
    "failed",
)

# Node lifecycle event kinds — LIFECYCLE ONLY (not a bridge/job execution event system).
MEMORY_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "updated",
    "compiled",
    "marked_stale",
    "merged",
    "archived",
    "failed",
)


V103_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_memory_nodes (
      node_id TEXT PRIMARY KEY,
      node_type TEXT NOT NULL CHECK(node_type IN ({_csv(MEMORY_NODE_TYPE_VALUES)})),
      canonical_name TEXT NOT NULL,
      normalized_name TEXT NOT NULL,
      aliases_json TEXT,
      domain TEXT,
      status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ({_csv(MEMORY_NODE_STATUS_VALUES)})),
      review_tier TEXT CHECK(review_tier IS NULL OR review_tier IN
        ({_csv(MEMORY_REVIEW_TIER_VALUES)})),
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      source_count INTEGER NOT NULL DEFAULT 0 CHECK(source_count >= 0),
      claim_count INTEGER NOT NULL DEFAULT 0 CHECK(claim_count >= 0),
      mention_count INTEGER NOT NULL DEFAULT 0 CHECK(mention_count >= 0),
      compilation_count INTEGER NOT NULL DEFAULT 0 CHECK(compilation_count >= 0),
      input_digest TEXT,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_nodes_type "
    "ON assistant_memory_nodes(node_type);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_nodes_norm "
    "ON assistant_memory_nodes(normalized_name);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_nodes_status "
    "ON assistant_memory_nodes(status, updated_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_memory_mentions (
      mention_id TEXT PRIMARY KEY,
      node_id TEXT NOT NULL,
      mention_type TEXT NOT NULL CHECK(mention_type IN ({_csv(MEMORY_MENTION_TYPE_VALUES)})),
      mention_text TEXT,
      -- provenance (at least one anchor required)
      source_id TEXT,
      note_rel_path TEXT,
      claim_id TEXT,
      job_id TEXT,
      receipt_id TEXT,
      pack_id TEXT,
      pack_item_id TEXT,
      evidence_excerpt TEXT,
      source_digest TEXT,
      card_digest TEXT,
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      review_tier TEXT CHECK(review_tier IS NULL OR review_tier IN
        ({_csv(MEMORY_REVIEW_TIER_VALUES)})),
      source_state TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL OR claim_id IS NOT NULL
            OR receipt_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_mentions_node "
    "ON assistant_memory_mentions(node_id, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_mentions_source "
    "ON assistant_memory_mentions(source_id);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_mentions_claim "
    "ON assistant_memory_mentions(claim_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_memory_compilations (
      compilation_id TEXT PRIMARY KEY,
      node_id TEXT NOT NULL,
      compile_type TEXT NOT NULL CHECK(compile_type IN ({_csv(MEMORY_COMPILE_TYPE_VALUES)})),
      summary TEXT,
      key_points_json TEXT,
      open_questions_json TEXT,
      risks_json TEXT,
      preferences_json TEXT,
      source_count INTEGER NOT NULL DEFAULT 0 CHECK(source_count >= 0),
      claim_count INTEGER NOT NULL DEFAULT 0 CHECK(claim_count >= 0),
      pack_count INTEGER NOT NULL DEFAULT 0 CHECK(pack_count >= 0),
      mention_count INTEGER NOT NULL DEFAULT 0 CHECK(mention_count >= 0),
      input_digest TEXT,
      output_digest TEXT,
      stale_count INTEGER NOT NULL DEFAULT 0 CHECK(stale_count >= 0),
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      review_tier TEXT CHECK(review_tier IS NULL OR review_tier IN
        ({_csv(MEMORY_REVIEW_TIER_VALUES)})),
      status TEXT NOT NULL DEFAULT 'built'
        CHECK(status IN ({_csv(MEMORY_COMPILATION_STATUS_VALUES)})),
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_compilations_node "
    "ON assistant_memory_compilations(node_id, compile_type, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_compilations_status "
    "ON assistant_memory_compilations(status);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_memory_events (
      event_id TEXT PRIMARY KEY,
      node_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(MEMORY_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_memory_events_node "
    "ON assistant_memory_events(node_id, created_at);",
]
