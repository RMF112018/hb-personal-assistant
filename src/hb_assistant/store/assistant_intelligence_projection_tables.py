"""V106 — Review-Aware Intelligence Projections (N8C-10).

Durable, bounded, review-aware **read products** materialized from the advisory records (N8C-4…N8C-8) and
the N8C-9 review overlay. They let a downstream consumer (ChatGPT / frontend / a future N8D job) ask "which
intelligence records are operator-accepted / still candidate / excluded, and what is the trusted context
packet" WITHOUT rehydrating every source table — and WITHOUT mutating any source or review record.

  * ``assistant_intelligence_projections`` — projection headers (type, scope, filter policy, budget,
    digests, per-inclusion counts).
  * ``assistant_intelligence_projection_items`` — bounded items linked back to their source/advisory/review
    records, each classified by effective review state into an ``inclusion_state`` (trusted / candidate /
    excluded / …). Items store only BOUNDED excerpts + ids/digests/state — never a raw source/card/vault
    body, a full enrichment ``result_json``, a full context-pack export, a full memory compilation, a full
    review-item payload, or a raw prompt/response. Excluded (``included=0``) items keep target ids, effective
    state, exclusion reason, and digests but carry no unnecessary content.
  * ``assistant_intelligence_projection_receipts`` — build receipts proving reproducibility + budget/filter
    accounting (input/output digests, counts, dropped/truncated).
  * ``assistant_intelligence_projection_events`` — append-only lifecycle log (created / built / exported /
    marked_stale / marked_superseded / failed). LIFECYCLE ONLY — NOT a bridge/job execution event system
    (that is N8D, which this slice must not touch or duplicate).

Narrow and projection-owned. NOT a graph schema, NOT a workflow/bridge/job schema, NOT a task executor. A
projection is a materialized read product, never source truth: it NEVER converts a candidate record into
accepted truth, and effective state is READ from the N8C-9 review tables, never written back. Additive
only; no existing table is touched. All four tables ship EMPTY; nothing populates them on startup — only an
explicit bounded ``intelligence build --apply`` command / service call writes rows. No lifespan / scheduler
/ watcher / worker path builds projections.
"""

from __future__ import annotations

from hb_assistant.store.assistant_review_tables import (
    EFFECTIVE_STATE_VALUES,
    REVIEW_STATE_VALUES,
    REVIEW_TARGET_KIND_VALUES,
)


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What kind of review-aware projection this is (defines the default inclusion policy).
PROJECTION_TYPE_VALUES: tuple[str, ...] = (
    "trusted_context",
    "candidate_context",
    "review_aware_context",
    "implementation_context",
    "project_intelligence",
    "decision_memory_context",
    "open_loop_context",
    "daily_brief_context",
    "unknown",
)

# Projection lifecycle.
PROJECTION_STATUS_VALUES: tuple[str, ...] = (
    "draft",
    "built",
    "stale",
    "superseded",
    "failed",
)

# How each item was classified for inclusion, derived from its effective review state + the policy.
INCLUSION_STATE_VALUES: tuple[str, ...] = (
    "trusted",
    "candidate",
    "excluded",
    "stale",
    "superseded",
    "not_required",
    "deferred",
    "unknown",
)

# Projection lifecycle event kinds — LIFECYCLE ONLY (not a bridge/job execution event system).
PROJECTION_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "built",
    "exported",
    "marked_stale",
    "marked_superseded",
    "failed",
)

# Effective/review-state enums are re-used from the N8C-9 review schema so the projection layer can never
# drift from the review overlay it reads.
_TARGET_KINDS = REVIEW_TARGET_KIND_VALUES
_REVIEW_STATES = REVIEW_STATE_VALUES
_EFFECTIVE_STATES = EFFECTIVE_STATE_VALUES


# Shared provenance + CHECK fragment (at least one anchor). ``target_id`` is separately NOT NULL; this
# additionally requires a concrete provenance anchor so an item can always be traced back to source.
_PROVENANCE_COLUMNS = """
      source_id TEXT,
      note_rel_path TEXT,
      claim_id TEXT,
      receipt_id TEXT,
      pack_id TEXT,
      pack_item_id TEXT,
      memory_node_id TEXT,
      memory_mention_id TEXT,
      compilation_id TEXT,
      decision_id TEXT,
      preference_id TEXT,
      open_loop_id TEXT,
      source_digest TEXT,
      card_digest TEXT,
      target_digest TEXT,
"""

_PROVENANCE_CHECK = """
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL OR claim_id IS NOT NULL
            OR receipt_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL
            OR memory_node_id IS NOT NULL OR memory_mention_id IS NOT NULL
            OR compilation_id IS NOT NULL OR decision_id IS NOT NULL
            OR preference_id IS NOT NULL OR open_loop_id IS NOT NULL)
"""


V106_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_intelligence_projections (
      projection_id TEXT PRIMARY KEY,
      projection_type TEXT NOT NULL CHECK(projection_type IN ({_csv(PROJECTION_TYPE_VALUES)})),
      title TEXT,
      objective TEXT,
      scope_json TEXT,
      filter_policy_json TEXT,
      budget_json TEXT,
      status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ({_csv(PROJECTION_STATUS_VALUES)})),
      input_digest TEXT,
      output_digest TEXT,
      trusted_count INTEGER NOT NULL DEFAULT 0,
      candidate_count INTEGER NOT NULL DEFAULT 0,
      excluded_count INTEGER NOT NULL DEFAULT 0,
      stale_count INTEGER NOT NULL DEFAULT 0,
      superseded_count INTEGER NOT NULL DEFAULT 0,
      item_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_intelligence_projections_type "
    "ON assistant_intelligence_projections(projection_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_intelligence_projections_input "
    "ON assistant_intelligence_projections(input_digest);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_intelligence_projection_items (
      projection_item_id TEXT PRIMARY KEY,
      projection_id TEXT NOT NULL,
      item_order INTEGER NOT NULL DEFAULT 0,
      target_kind TEXT NOT NULL CHECK(target_kind IN ({_csv(_TARGET_KINDS)})),
      target_id TEXT NOT NULL,
      review_item_id TEXT,
      disposition_id TEXT,
      effective_state TEXT CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      inclusion_state TEXT NOT NULL CHECK(inclusion_state IN ({_csv(INCLUSION_STATE_VALUES)})),
      review_state TEXT CHECK(review_state IS NULL OR review_state IN ({_csv(_REVIEW_STATES)})),
      title TEXT,
      summary TEXT,
      evidence_excerpt TEXT,
{_PROVENANCE_COLUMNS}      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      priority TEXT,
      token_estimate INTEGER NOT NULL DEFAULT 0,
      included INTEGER NOT NULL DEFAULT 0 CHECK(included IN (0, 1)),
      exclusion_reason TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
{_PROVENANCE_CHECK}    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_intelligence_projection_items_projection "
    "ON assistant_intelligence_projection_items(projection_id, item_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_intelligence_projection_items_inclusion "
    "ON assistant_intelligence_projection_items(projection_id, inclusion_state);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_intelligence_projection_items_target "
    "ON assistant_intelligence_projection_items(target_kind, target_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_intelligence_projection_receipts (
      projection_receipt_id TEXT PRIMARY KEY,
      projection_id TEXT NOT NULL,
      builder_version TEXT,
      input_digest TEXT,
      output_digest TEXT,
      filter_policy_json TEXT,
      budget_json TEXT,
      trusted_count INTEGER NOT NULL DEFAULT 0,
      candidate_count INTEGER NOT NULL DEFAULT 0,
      excluded_count INTEGER NOT NULL DEFAULT 0,
      stale_count INTEGER NOT NULL DEFAULT 0,
      superseded_count INTEGER NOT NULL DEFAULT 0,
      dropped_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_intelligence_projection_receipts_projection "
    "ON assistant_intelligence_projection_receipts(projection_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_intelligence_projection_events (
      event_id TEXT PRIMARY KEY,
      projection_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(PROJECTION_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_intelligence_projection_events_projection "
    "ON assistant_intelligence_projection_events(projection_id, created_at);",
]
