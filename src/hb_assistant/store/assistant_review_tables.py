"""V105 — Unified Review Queue, Disposition Ledger, and Review Events (N8C-9).

A source-backed operator **review overlay** over the advisory objects produced by N8C-4…N8C-8 (claims,
enrichment review, context-pack items, memory nodes/mentions/compilations, decision/preference/open-loop
records). It answers "what needs review / what was accepted, rejected, deferred, or marked not required /
what is stale or superseded" WITHOUT mutating any source table, executing any action, or adding a remote
write tool.

  * ``assistant_review_items`` — durable review-queue snapshots that POINT AT existing advisory records
    (they never replace or mutate them). Bounded review metadata only: target ids + digests, bounded
    title/summary/evidence_excerpt, bounded metadata — never a raw source/email body, a full
    enrichment ``result_json``, a full context-pack export, a full memory compilation, or a raw
    prompt/response.
  * ``assistant_review_dispositions`` — an APPEND-ONLY local/operator disposition ledger. Recording a
    disposition never mutates the source advisory record; the effective review state is COMPUTED from the
    review item + its latest disposition.
  * ``assistant_review_events`` — append-only review lifecycle log (created / updated /
    disposition_recorded / marked_stale / marked_superseded / failed). LIFECYCLE ONLY — NOT a bridge/job
    execution event system (that is N8D, which this slice must not touch or duplicate).

Narrow and overlay-based. NOT a workflow engine, NOT a task/action executor, NOT a bridge/job schema, NOT
a reminder/scheduler. Additive only; no existing table is touched. Every review item defaults to
``review_state='unreviewed'`` / ``effective_state='candidate'`` — nothing is auto-accepted, and building a
review item NEVER accepts the underlying claim/decision/memory record (candidate records stay
candidate/unreviewed). Dispositions are the ONLY way an item leaves the default state, and they write only
the review-overlay tables.

Invariants baked into the schema (DB is the backstop; the models validate first with clean errors):
  * every review item is anchored — ``target_kind``/``target_id`` are required and a table CHECK requires
    at least one provenance anchor (source_id / note_rel_path / claim_id / receipt_id / pack_id /
    pack_item_id / memory_node_id / memory_mention_id / compilation_id / decision_id / preference_id /
    open_loop_id);
  * target_kind / review_type / review_state / effective_state / disposition_type / event kinds are
    enum-constrained; confidence is 0..1;
  * text columns store only BOUNDED excerpts (the models cap them before write).

All three tables ship EMPTY; nothing populates them on startup — only an explicit bounded
``review build --apply`` / ``review disposition --apply`` command / service call writes rows. No lifespan /
scheduler / watcher / worker path builds review items or records dispositions.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What kind of advisory record a review item points at.
REVIEW_TARGET_KIND_VALUES: tuple[str, ...] = (
    "claim",
    "enrichment_receipt",
    "enrichment_review_item",
    "context_pack",
    "context_pack_item",
    "memory_node",
    "memory_mention",
    "memory_compilation",
    "decision",
    "preference",
    "open_loop",
    "unknown",
)

# The review lens applied to the target.
REVIEW_TYPE_VALUES: tuple[str, ...] = (
    "claim_review",
    "enrichment_review",
    "context_pack_review",
    "memory_review",
    "decision_review",
    "preference_review",
    "open_loop_review",
    "stale_review",
    "conflict_review",
    "unknown",
)

# Advisory review state (queue-facing). ``operator_*`` / deferred / not_required are set only by a
# disposition; stale / superseded are set by explicit lifecycle transitions.
REVIEW_STATE_VALUES: tuple[str, ...] = (
    "unreviewed",
    "needs_review",
    "operator_accepted",
    "operator_rejected",
    "deferred",
    "not_required",
    "stale",
    "superseded",
)

# Effective (downstream-facing) state. ``candidate`` = not yet operator-approved; downstream read models
# should treat only ``accepted`` as operator-approved.
EFFECTIVE_STATE_VALUES: tuple[str, ...] = (
    "candidate",
    "accepted",
    "rejected",
    "deferred",
    "not_required",
    "stale",
    "superseded",
)

# Local/operator disposition kinds. Dispositions are append-only ledger events — never upserts.
DISPOSITION_TYPE_VALUES: tuple[str, ...] = (
    "accept",
    "reject",
    "defer",
    "mark_not_required",
    "mark_stale",
    "mark_superseded",
    "request_more_context",
    "unknown",
)

# Review lifecycle event kinds — LIFECYCLE ONLY (not a bridge/job execution event system).
REVIEW_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "updated",
    "disposition_recorded",
    "marked_stale",
    "marked_superseded",
    "failed",
)


# Shared provenance + CHECK fragment (at least one anchor). Kept as a constant so the invariant can't
# drift. ``target_id`` is separately NOT NULL; this CHECK additionally requires a concrete provenance
# anchor so a review item can always be traced back to source evidence.
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
      evidence_excerpt TEXT,
      evidence_location TEXT,
      source_digest TEXT,
      card_digest TEXT,
"""

_PROVENANCE_CHECK = """
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL OR claim_id IS NOT NULL
            OR receipt_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL
            OR memory_node_id IS NOT NULL OR memory_mention_id IS NOT NULL
            OR compilation_id IS NOT NULL OR decision_id IS NOT NULL
            OR preference_id IS NOT NULL OR open_loop_id IS NOT NULL)
"""


V105_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_review_items (
      review_item_id TEXT PRIMARY KEY,
      target_kind TEXT NOT NULL CHECK(target_kind IN ({_csv(REVIEW_TARGET_KIND_VALUES)})),
      target_id TEXT NOT NULL,
      target_digest TEXT,
      target_state_digest TEXT,
      review_type TEXT NOT NULL CHECK(review_type IN ({_csv(REVIEW_TYPE_VALUES)})),
      title TEXT,
      summary TEXT,
      review_state TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK(review_state IN ({_csv(REVIEW_STATE_VALUES)})),
      effective_state TEXT NOT NULL DEFAULT 'candidate'
        CHECK(effective_state IN ({_csv(EFFECTIVE_STATE_VALUES)})),
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      priority TEXT,
      stale INTEGER NOT NULL DEFAULT 0 CHECK(stale IN (0, 1)),
      superseded INTEGER NOT NULL DEFAULT 0 CHECK(superseded IN (0, 1)),
{_PROVENANCE_COLUMNS}      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
{_PROVENANCE_CHECK}    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_review_items_target "
    "ON assistant_review_items(target_kind, target_id, review_state);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_review_items_type "
    "ON assistant_review_items(review_type, review_state);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_review_items_effective "
    "ON assistant_review_items(effective_state);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_review_dispositions (
      disposition_id TEXT PRIMARY KEY,
      review_item_id TEXT NOT NULL,
      target_kind TEXT CHECK(target_kind IS NULL OR target_kind IN ({_csv(REVIEW_TARGET_KIND_VALUES)})),
      target_id TEXT,
      disposition_type TEXT NOT NULL
        CHECK(disposition_type IN ({_csv(DISPOSITION_TYPE_VALUES)})),
      from_review_state TEXT,
      to_review_state TEXT,
      from_effective_state TEXT,
      to_effective_state TEXT,
      operator_id TEXT,
      reason TEXT,
      evidence_note TEXT,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_review_dispositions_item "
    "ON assistant_review_dispositions(review_item_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_review_events (
      event_id TEXT PRIMARY KEY,
      review_item_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(REVIEW_EVENT_TYPE_VALUES)})),
      from_state TEXT,
      to_state TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_review_events_item "
    "ON assistant_review_events(review_item_id, created_at);",
]
