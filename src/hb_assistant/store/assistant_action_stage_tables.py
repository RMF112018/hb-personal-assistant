"""V110 — Action Staging, Not Action Execution (N8C-19).

Durable, source-backed, operator-review-required staging of proposed follow-up CANDIDATES derived from the
N8C-17 workflow CONTEXT envelope (read-only) + N8C-18 ADVISORY feedback recommendations (read-only). A stage
records what an operator *might* do next — it NEVER executes anything, never contacts an external system,
never changes a review state, and never mutates the workflow/feedback/review/source/draft/packet/projection/
context-pack/decision/preference/open-loop records it reads.

  * ``assistant_action_stages`` — stage headers (stage_type, workflow lineage, stage-record lifecycle status
    draft/staged/superseded, digests, counts, the fixed no-execution / staged-only / staging-only /
    preserve-review-state policy). There is deliberately NO ``sent`` / ``scheduled`` / ``completed`` /
    ``executed`` / ``dispatched`` / ``emailed`` / ``n8d_job`` field anywhere.
  * ``assistant_action_stage_items`` — one proposed follow-up CANDIDATE each. Every item is pinned to
    ``execution_status='not_executed'``, ``external_system='none'``, ``external_ref IS NULL``, and
    ``requires_operator_review=1`` by CHECK. Its ``staged_state`` is only ``candidate`` or ``blocked`` —
    never ``active`` / ``executed`` / ``sent``. It carries preserved provenance anchors (bounded ids only,
    no body) + copied review/effective state (metadata, never written back).
  * ``assistant_action_stage_citations`` — bounded provenance bridge to the existing artifacts a staged item
    is grounded in (workflow citations / source refs / anchors). Provenance CHECK requires ≥1 anchor.
  * ``assistant_action_stage_receipts`` — derivation receipts (request/source-context/input/output digests,
    counts) for reproducibility + accounting.
  * ``assistant_action_stage_events`` — append-only stage-record lifecycle log (created / staged / item_added
    / citation_added / superseded). LIFECYCLE OF THE STAGE RECORD ONLY — NOT an execution/dispatch ledger.

Narrow and stage-owned. NOT an executor, NOT an external-task creator, NOT a review-disposition writer, NOT a
scheduler, NOT N8D. Additive only; no existing table is touched. All five tables ship EMPTY; only an explicit
bounded ``action-stage build --apply`` command / builder call writes rows.
"""

from __future__ import annotations

from hb_assistant.store.assistant_review_tables import (
    EFFECTIVE_STATE_VALUES,
    REVIEW_STATE_VALUES,
)


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# The kind of stage produced (mirrors the N8C-17 workflow the context came from). A stage bundles candidate
# follow-ups; it never names an external delivery channel.
STAGE_TYPE_VALUES: tuple[str, ...] = (
    "daily_brief_actions",
    "meeting_follow_ups",
    "project_actions",
    "open_loop_actions",
    "review_follow_ups",
    "mixed_actions",
    "unknown",
)

# Stage-RECORD lifecycle ONLY (never an execution state). ``superseded`` means a newer stage of the same
# lineage replaced this one; it never means an action ran.
STAGE_STATUS_VALUES: tuple[str, ...] = (
    "draft",
    "staged",
    "superseded",
)

# What an operator might do next — all INTERNAL-REVIEW kinds. There is intentionally NO send_email /
# create_task / schedule_meeting / dispatch / external-execution kind. Every kind resolves to human review.
ACTION_KIND_VALUES: tuple[str, ...] = (
    "open_loop_follow_up",
    "review_candidate",
    "source_review",
    "project_risk_review",
    "information_gap_review",
    "decision_review",
    "preference_review",
    "human_follow_up",
    "unknown",
)

# A staged item is only ever a CANDIDATE or BLOCKED — never active/executed/sent. ``blocked`` means the item
# was recognized but withheld from candidacy (e.g. an execution-like advisory step, or a terminal source).
ITEM_STAGE_STATE_VALUES: tuple[str, ...] = (
    "candidate",
    "blocked",
)

# Append-only stage-record lifecycle events. NOT execution/dispatch events.
STAGE_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "staged",
    "item_added",
    "citation_added",
    "superseded",
)

_REVIEW_STATES = REVIEW_STATE_VALUES
_EFFECTIVE_STATES = EFFECTIVE_STATE_VALUES

# Fixed, non-overridable stage policy (mirrored in the models + asserted by tests). Pinned by CHECK so a stage
# row can never claim execution, an external delivery, a review-state change, or new source reads.
_STAGE_POLICY = """
      action_policy TEXT NOT NULL DEFAULT 'no_execution' CHECK(action_policy = 'no_execution'),
      execution_policy TEXT NOT NULL DEFAULT 'staged_only' CHECK(execution_policy = 'staged_only'),
      workflow_policy TEXT NOT NULL DEFAULT 'staging_only' CHECK(workflow_policy = 'staging_only'),
      review_policy TEXT NOT NULL DEFAULT 'preserve_review_state' CHECK(review_policy = 'preserve_review_state'),
      citation_policy TEXT NOT NULL DEFAULT 'preserve_citations' CHECK(citation_policy = 'preserve_citations'),
      source_policy TEXT NOT NULL DEFAULT 'use_existing_artifacts_only'
        CHECK(source_policy = 'use_existing_artifacts_only'),
      requires_operator_review INTEGER NOT NULL DEFAULT 1 CHECK(requires_operator_review = 1),
"""

# Optional typed upstream anchors carried on a staged item / citation for preserved provenance (bounded ids
# only — never a body/payload).
_STAGE_ITEM_PROVENANCE = """
      workflow_id TEXT,
      draft_id TEXT,
      packet_id TEXT,
      projection_item_id TEXT,
      context_pack_id TEXT,
      memory_node_id TEXT,
      decision_id TEXT,
      preference_id TEXT,
      open_loop_id TEXT,
      review_item_id TEXT,
      claim_id TEXT,
      citation_id TEXT,
      feedback_id TEXT,
      recommendation_id TEXT,
      source_id TEXT,
      source_ref TEXT,
      source_root_key TEXT,
      rel_path TEXT,
      note_rel_path TEXT,
"""


V110_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_action_stages (
      stage_id TEXT PRIMARY KEY,
      stage_type TEXT NOT NULL CHECK(stage_type IN ({_csv(STAGE_TYPE_VALUES)})),
      workflow_type TEXT,
      workflow_id TEXT,
      title TEXT,
      status TEXT NOT NULL DEFAULT 'staged' CHECK(status IN ({_csv(STAGE_STATUS_VALUES)})),
{_STAGE_POLICY}      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      request_digest TEXT,
      source_context_digest TEXT,
      input_digest TEXT,
      output_digest TEXT,
      stage_policy_json TEXT,
      budget_json TEXT,
      item_count INTEGER NOT NULL DEFAULT 0,
      blocked_count INTEGER NOT NULL DEFAULT 0,
      citation_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stages_type "
    "ON assistant_action_stages(stage_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stages_workflow "
    "ON assistant_action_stages(workflow_type, workflow_id);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stages_lineage "
    "ON assistant_action_stages(stage_type, workflow_type, request_digest, status);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_action_stage_items (
      stage_item_id TEXT PRIMARY KEY,
      stage_id TEXT NOT NULL,
      item_order INTEGER NOT NULL DEFAULT 0,
      action_kind TEXT NOT NULL CHECK(action_kind IN ({_csv(ACTION_KIND_VALUES)})),
      staged_state TEXT NOT NULL DEFAULT 'candidate' CHECK(staged_state IN ({_csv(ITEM_STAGE_STATE_VALUES)})),
      source_section TEXT,
      title TEXT,
      detail TEXT,
      block_reason TEXT,
      execution_status TEXT NOT NULL DEFAULT 'not_executed'
        CHECK(execution_status = 'not_executed'),
      external_system TEXT NOT NULL DEFAULT 'none' CHECK(external_system = 'none'),
      external_ref TEXT CHECK(external_ref IS NULL),
      requires_operator_review INTEGER NOT NULL DEFAULT 1 CHECK(requires_operator_review = 1),
      target_kind TEXT,
      target_id TEXT,
{_STAGE_ITEM_PROVENANCE}      review_state TEXT CHECK(review_state IS NULL OR review_state IN ({_csv(_REVIEW_STATES)})),
      effective_state TEXT
        CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      item_digest TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stage_items_stage "
    "ON assistant_action_stage_items(stage_id, item_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stage_items_kind "
    "ON assistant_action_stage_items(action_kind, staged_state);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stage_items_target "
    "ON assistant_action_stage_items(target_kind, target_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_action_stage_citations (
      stage_citation_id TEXT PRIMARY KEY,
      stage_id TEXT NOT NULL,
      stage_item_id TEXT NOT NULL,
      citation_order INTEGER NOT NULL DEFAULT 0,
      citation_type TEXT,
      target_kind TEXT,
      target_id TEXT,
      workflow_id TEXT,
      draft_id TEXT,
      packet_id TEXT,
      projection_item_id TEXT,
      context_pack_id TEXT,
      memory_node_id TEXT,
      decision_id TEXT,
      preference_id TEXT,
      open_loop_id TEXT,
      review_item_id TEXT,
      claim_id TEXT,
      citation_id TEXT,
      feedback_id TEXT,
      recommendation_id TEXT,
      source_id TEXT,
      source_ref TEXT,
      source_root_key TEXT,
      rel_path TEXT,
      note_rel_path TEXT,
      citation_label TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
      CHECK (
        target_id IS NOT NULL OR workflow_id IS NOT NULL OR draft_id IS NOT NULL OR packet_id IS NOT NULL
        OR projection_item_id IS NOT NULL OR context_pack_id IS NOT NULL OR memory_node_id IS NOT NULL
        OR decision_id IS NOT NULL OR preference_id IS NOT NULL OR open_loop_id IS NOT NULL
        OR review_item_id IS NOT NULL OR claim_id IS NOT NULL OR citation_id IS NOT NULL
        OR feedback_id IS NOT NULL OR recommendation_id IS NOT NULL OR source_id IS NOT NULL
        OR source_ref IS NOT NULL OR rel_path IS NOT NULL OR note_rel_path IS NOT NULL
      )
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stage_citations_stage "
    "ON assistant_action_stage_citations(stage_id, stage_item_id, citation_order);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_action_stage_receipts (
      stage_receipt_id TEXT PRIMARY KEY,
      stage_id TEXT NOT NULL,
      builder_version TEXT,
      request_digest TEXT,
      source_context_digest TEXT,
      input_digest TEXT,
      output_digest TEXT,
      item_count INTEGER NOT NULL DEFAULT 0,
      blocked_count INTEGER NOT NULL DEFAULT 0,
      citation_count INTEGER NOT NULL DEFAULT 0,
      dropped_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stage_receipts_stage "
    "ON assistant_action_stage_receipts(stage_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_action_stage_events (
      event_id TEXT PRIMARY KEY,
      stage_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(STAGE_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_action_stage_events_stage "
    "ON assistant_action_stage_events(stage_id, created_at);",
]
