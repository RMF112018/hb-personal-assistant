"""V102 — Context-Pack tables (N8C-6).

Durable, reproducible, source-linked **intelligence packets** assembled from the existing N8C
substrate — sources/cards (N8C-2), navigation (N8C-3), candidate claims (N8C-4, V100), and Qwen
enrichment receipts (N8C-5, V101). A pack is a bounded, digest/stale-aware selection of provenance
items with a per-build reproducibility receipt and an append-only lifecycle log.

Narrow and neutral — NOT a graph schema, NOT a bridge/job/execution schema (that is N8D, which this
slice must not touch or duplicate). Additive only; no existing table is touched. The enrichment-review
read model that feeds pack assembly is *derived* at read time (no table of its own).

Invariants baked into the schema (DB is the backstop; the repository/models validate first with clean
errors):
  * a pack item is provenance-backed — `CHECK(source_id/note_rel_path/claim_id/receipt_id present)`;
  * `pack_type` / `status` / item `item_type` / `review_tier` / event `event_type` are enum-constrained;
  * ``truncated`` / ``included`` are 0/1; counts are non-negative;
  * pack items carry only BOUNDED selected excerpts (`content_excerpt`/`evidence_excerpt`) — never a
    full enrichment ``result_json``; the source enrichment output is linked via ``receipt_id`` +
    ``result_digest`` (the model bounds every text column before write).

All four tables ship EMPTY; nothing populates them on startup — only an explicit bounded
``context-pack build --apply`` command / service call writes rows. No lifespan / scheduler / watcher /
worker path builds a pack.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What a pack is assembled for. Minimal useful set for N8C-6.
CONTEXT_PACK_TYPE_VALUES: tuple[str, ...] = (
    "enrichment_review",
    "source_review",
    "implementation_context",
)

# Pack lifecycle. A pack is `draft` while previewing, `built` once persisted, `stale` when an input
# digest has drifted, `superseded` when a newer pack_id replaces it, `failed` on a build error.
CONTEXT_PACK_STATUS_VALUES: tuple[str, ...] = (
    "draft",
    "built",
    "stale",
    "superseded",
    "failed",
)

# What a single pack item is anchored to.
CONTEXT_PACK_ITEM_TYPE_VALUES: tuple[str, ...] = (
    "source_summary",
    "claim_candidate",
    "backlink_suggestion",
    "source",
    "unknown",
)

# Advisory review tier for an item (distinct from a claim's review_state; nothing here accepts a
# claim). Mirrors the enrichment-review read-model tiers.
CONTEXT_PACK_REVIEW_TIER_VALUES: tuple[str, ...] = (
    "safe_summary",
    "needs_operator_review",
    "source_stale",
    "claim_candidate",
    "link_candidate",
    "low_confidence",
    "conflict_or_contradiction",
)

# Pack lifecycle event kinds — LIFECYCLE ONLY. This is not a bridge/job/execution event log.
CONTEXT_PACK_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "built",
    "marked_stale",
    "superseded",
)


V102_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_context_packs (
      pack_id TEXT PRIMARY KEY,
      pack_type TEXT NOT NULL CHECK(pack_type IN ({_csv(CONTEXT_PACK_TYPE_VALUES)})),
      title TEXT,
      objective TEXT,
      scope_json TEXT,
      budget_json TEXT,
      status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ({_csv(CONTEXT_PACK_STATUS_VALUES)})),
      created_by TEXT,
      builder_version TEXT,
      input_digest TEXT,
      output_digest TEXT,
      source_count INTEGER NOT NULL DEFAULT 0 CHECK(source_count >= 0),
      claim_count INTEGER NOT NULL DEFAULT 0 CHECK(claim_count >= 0),
      receipt_count INTEGER NOT NULL DEFAULT 0 CHECK(receipt_count >= 0),
      item_count INTEGER NOT NULL DEFAULT 0 CHECK(item_count >= 0),
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      stale_count INTEGER NOT NULL DEFAULT 0 CHECK(stale_count >= 0),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_context_packs_type "
    "ON assistant_context_packs(pack_type);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_context_packs_status "
    "ON assistant_context_packs(status, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_context_pack_items (
      pack_item_id TEXT PRIMARY KEY,
      pack_id TEXT NOT NULL,
      item_order INTEGER NOT NULL DEFAULT 0 CHECK(item_order >= 0),
      item_type TEXT NOT NULL CHECK(item_type IN ({_csv(CONTEXT_PACK_ITEM_TYPE_VALUES)})),
      -- provenance (at least one anchor is required)
      source_id TEXT,
      note_rel_path TEXT,
      claim_id TEXT,
      job_id TEXT,
      receipt_id TEXT,
      title TEXT,
      -- BOUNDED selected excerpts only; the model caps these before write. Never a full result_json.
      content_excerpt TEXT,
      evidence_excerpt TEXT,
      source_digest TEXT,
      card_digest TEXT,
      result_digest TEXT,
      source_state TEXT,
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      review_tier TEXT CHECK(review_tier IS NULL OR review_tier IN
        ({_csv(CONTEXT_PACK_REVIEW_TIER_VALUES)})),
      token_estimate INTEGER NOT NULL DEFAULT 0 CHECK(token_estimate >= 0),
      included INTEGER NOT NULL DEFAULT 1 CHECK(included IN (0, 1)),
      exclusion_reason TEXT,
      metadata_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL
            OR claim_id IS NOT NULL OR receipt_id IS NOT NULL)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_context_pack_items_pack "
    "ON assistant_context_pack_items(pack_id, item_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_context_pack_items_source "
    "ON assistant_context_pack_items(source_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_context_pack_receipts (
      receipt_id TEXT PRIMARY KEY,
      pack_id TEXT NOT NULL,
      builder_version TEXT,
      input_digest TEXT,
      output_digest TEXT,
      scope_json TEXT,
      budget_json TEXT,
      included_count INTEGER NOT NULL DEFAULT 0 CHECK(included_count >= 0),
      excluded_count INTEGER NOT NULL DEFAULT 0 CHECK(excluded_count >= 0),
      source_count INTEGER NOT NULL DEFAULT 0 CHECK(source_count >= 0),
      claim_count INTEGER NOT NULL DEFAULT 0 CHECK(claim_count >= 0),
      receipt_count INTEGER NOT NULL DEFAULT 0 CHECK(receipt_count >= 0),
      stale_count INTEGER NOT NULL DEFAULT 0 CHECK(stale_count >= 0),
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      total_chars INTEGER NOT NULL DEFAULT 0 CHECK(total_chars >= 0),
      total_token_estimate INTEGER NOT NULL DEFAULT 0 CHECK(total_token_estimate >= 0),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_context_pack_receipts_pack "
    "ON assistant_context_pack_receipts(pack_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_context_pack_events (
      event_id TEXT PRIMARY KEY,
      pack_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(CONTEXT_PACK_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_context_pack_events_pack "
    "ON assistant_context_pack_events(pack_id, created_at);",
]
