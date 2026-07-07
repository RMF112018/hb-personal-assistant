"""V109 — Feedback Capture and Review Loop Integration (N8C-18).

Durable, bounded, feedback-owned records capturing OPERATOR feedback on existing N8C artifacts (workflow
results/sections/artifacts, answer drafts, research packets, citations, source refs, review items, claims,
memory, decisions, preferences, open loops, advisory next steps) and integrating that feedback into the
review loop as ADVISORY, operator-review-required recommendations — WITHOUT changing any review disposition,
source truth, workflow record, packet/draft/projection/context-pack, or open-loop/decision/preference record.

  * ``assistant_feedback_records`` — feedback headers (feedback_type, bounded note, feedback-record lifecycle
    status, digests, counts, the fixed no-execution / feedback-only / advisory-review-loop policy). There is
    deliberately NO ``accept`` / ``reject`` / ``defer`` / ``dispose`` / ``executed`` / ``sent`` / ``scheduled``
    field anywhere: feedback is advisory input to the review loop, never a review disposition and never an
    action.
  * ``assistant_feedback_targets`` — what each feedback record is about, with preserved provenance. Every
    target carries a mandatory ``target_kind`` + ``target_id`` plus optional typed upstream anchors; it never
    stores a raw source/card/vault body, a raw email body, a full packet/draft/pack payload, or a raw
    prompt/response — bounded metadata only.
  * ``assistant_feedback_recommendations`` — deterministic ADVISORY review-loop recommendations derived from a
    feedback record (suggest_review / suggest_more_context / suggest_source_check / suggest_relabel_* /
    suggest_exclude / …). Advisory only: a recommendation is a suggestion FOR operator review, never an applied
    relabel, never an accept/reject/defer/dispose, never a state change.
  * ``assistant_feedback_receipts`` — derivation receipts proving reproducibility + accounting (input/output
    digests, counts).
  * ``assistant_feedback_events`` — append-only feedback-record lifecycle log (created / linked / recommended /
    acknowledged / resolved / superseded). LIFECYCLE OF THE FEEDBACK RECORD ONLY — NOT a review-disposition
    ledger, NOT a bridge/job/action/workflow execution event system (that is N8D, untouched here). If
    ``resolved``/``acknowledged`` is used it means the feedback record's own lifecycle, never a review
    disposition.

Narrow and feedback-owned. NOT a review-disposition writer, NOT an action stager, NOT an executor, NOT a
final-answer generator. Feedback NEVER converts a candidate record into accepted truth, NEVER closes an open
loop, NEVER mutates source/workflow/review/packet/draft/projection/context-pack/decision/preference/open-loop
records — it only records bounded operator input and derives advisory recommendations. Additive only; no
existing table is touched. All five tables ship EMPTY; nothing populates them on startup — only an explicit
bounded ``feedback add --apply`` command / service call writes rows. No lifespan / scheduler / watcher /
worker path writes feedback.
"""

from __future__ import annotations

from hb_assistant.store.assistant_review_tables import (
    EFFECTIVE_STATE_VALUES,
    REVIEW_STATE_VALUES,
)


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What the operator is giving feedback about. Kinds mirror the N8C artifact vocabulary the workflow layer
# already surfaces; a feedback record targets one or more of these via assistant_feedback_targets.
FEEDBACK_TARGET_KIND_VALUES: tuple[str, ...] = (
    "workflow_result",
    "workflow_section",
    "workflow_artifact",
    "answer_draft",
    "answer_draft_section",
    "research_packet",
    "research_packet_item",
    "citation",
    "source_ref",
    "source_file_metadata",
    "context_pack",
    "intelligence_projection",
    "projection_item",
    "review_item",
    "claim",
    "memory_node",
    "memory_mention",
    "decision",
    "preference",
    "open_loop",
    "advisory_next_step",
    "unknown",
)

# The nature of the operator's feedback. NONE of these applies a change; they are advisory signals.
FEEDBACK_TYPE_VALUES: tuple[str, ...] = (
    "useful",
    "not_useful",
    "incorrect",
    "incomplete",
    "needs_review",
    "needs_more_context",
    "wrong_source",
    "missing_source",
    "wrong_review_label",
    "candidate_should_be_trusted",
    "trusted_should_be_candidate",
    "should_be_excluded",
    "duplicate",
    "stale",
    "operator_note",
    "unknown",
)

# Feedback-RECORD lifecycle ONLY (never a review disposition). ``resolved`` means the feedback record itself
# was dealt with, NOT that a review item was accepted/rejected/deferred.
FEEDBACK_STATUS_VALUES: tuple[str, ...] = (
    "open",
    "acknowledged",
    "resolved",
    "superseded",
)

# Deterministic ADVISORY recommendations derived from a feedback record. Every value is a SUGGESTION for the
# operator's review loop — never an applied action or state change. No accept/reject/defer/dispose value exists.
RECOMMENDATION_TYPE_VALUES: tuple[str, ...] = (
    "suggest_review",
    "suggest_more_context",
    "suggest_source_check",
    "suggest_relabel_candidate",
    "suggest_relabel_trusted",
    "suggest_exclude",
    "suggest_deduplicate",
    "operator_note",
    "unknown",
)

# Append-only feedback-record lifecycle events. NOT review-disposition or execution events.
FEEDBACK_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "linked",
    "recommended",
    "acknowledged",
    "resolved",
    "superseded",
)

# Review/effective-state enums are RE-USED from the N8C-9 review schema so the feedback layer can never drift
# from the review overlay it reads (it copies these as bounded metadata; it never writes them back).
_REVIEW_STATES = REVIEW_STATE_VALUES
_EFFECTIVE_STATES = EFFECTIVE_STATE_VALUES

# Fixed, non-overridable policy (mirrored in the models + asserted by tests). Pinned by CHECK so a row can
# never claim execution, a review-disposition write, or source mutation.
_FEEDBACK_POLICY = """
      action_policy TEXT NOT NULL DEFAULT 'no_execution' CHECK(action_policy = 'no_execution'),
      execution_policy TEXT NOT NULL DEFAULT 'feedback_only' CHECK(execution_policy = 'feedback_only'),
      review_policy TEXT NOT NULL DEFAULT 'advisory_review_loop' CHECK(review_policy = 'advisory_review_loop'),
      source_policy TEXT NOT NULL DEFAULT 'preserve_source_truth' CHECK(source_policy = 'preserve_source_truth'),
      citation_policy TEXT NOT NULL DEFAULT 'preserve_citations' CHECK(citation_policy = 'preserve_citations'),
      requires_operator_review INTEGER NOT NULL DEFAULT 1 CHECK(requires_operator_review = 1),
"""

# Optional typed upstream anchors carried on a feedback target for richer provenance (in addition to the
# mandatory target_kind + target_id). Bounded ids only — never a body/payload.
_TARGET_PROVENANCE_COLUMNS = """
      workflow_id TEXT,
      workflow_type TEXT,
      workflow_section TEXT,
      draft_id TEXT,
      draft_section_id TEXT,
      packet_id TEXT,
      packet_item_id TEXT,
      projection_id TEXT,
      projection_item_id TEXT,
      context_pack_id TEXT,
      memory_node_id TEXT,
      memory_mention_id TEXT,
      decision_id TEXT,
      preference_id TEXT,
      open_loop_id TEXT,
      review_item_id TEXT,
      claim_id TEXT,
      citation_id TEXT,
      source_id TEXT,
      source_ref TEXT,
      source_root_key TEXT,
      rel_path TEXT,
      note_rel_path TEXT,
"""


V109_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_feedback_records (
      feedback_id TEXT PRIMARY KEY,
      feedback_type TEXT NOT NULL CHECK(feedback_type IN ({_csv(FEEDBACK_TYPE_VALUES)})),
      note TEXT,
      workflow_type TEXT,
      workflow_id TEXT,
      status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ({_csv(FEEDBACK_STATUS_VALUES)})),
{_FEEDBACK_POLICY}      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      input_digest TEXT,
      output_digest TEXT,
      target_count INTEGER NOT NULL DEFAULT 0,
      recommendation_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_records_type "
    "ON assistant_feedback_records(feedback_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_records_workflow "
    "ON assistant_feedback_records(workflow_id);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_records_input "
    "ON assistant_feedback_records(input_digest);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_feedback_targets (
      feedback_target_id TEXT PRIMARY KEY,
      feedback_id TEXT NOT NULL,
      target_order INTEGER NOT NULL DEFAULT 0,
      target_kind TEXT NOT NULL CHECK(target_kind IN ({_csv(FEEDBACK_TARGET_KIND_VALUES)})),
      target_id TEXT NOT NULL,
      target_label TEXT,
{_TARGET_PROVENANCE_COLUMNS}      target_digest TEXT,
      review_state TEXT CHECK(review_state IS NULL OR review_state IN ({_csv(_REVIEW_STATES)})),
      effective_state TEXT CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_targets_feedback "
    "ON assistant_feedback_targets(feedback_id, target_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_targets_target "
    "ON assistant_feedback_targets(target_kind, target_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_feedback_recommendations (
      recommendation_id TEXT PRIMARY KEY,
      feedback_id TEXT NOT NULL,
      recommendation_order INTEGER NOT NULL DEFAULT 0,
      recommendation_type TEXT NOT NULL
        CHECK(recommendation_type IN ({_csv(RECOMMENDATION_TYPE_VALUES)})),
      target_kind TEXT CHECK(target_kind IS NULL OR target_kind IN ({_csv(FEEDBACK_TARGET_KIND_VALUES)})),
      target_id TEXT,
      rationale TEXT,
      review_policy TEXT NOT NULL DEFAULT 'advisory_review_loop'
        CHECK(review_policy = 'advisory_review_loop'),
      requires_operator_review INTEGER NOT NULL DEFAULT 1 CHECK(requires_operator_review = 1),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_recommendations_feedback "
    "ON assistant_feedback_recommendations(feedback_id, recommendation_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_recommendations_target "
    "ON assistant_feedback_recommendations(target_kind, target_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_feedback_receipts (
      feedback_receipt_id TEXT PRIMARY KEY,
      feedback_id TEXT NOT NULL,
      builder_version TEXT,
      input_digest TEXT,
      output_digest TEXT,
      target_count INTEGER NOT NULL DEFAULT 0,
      recommendation_count INTEGER NOT NULL DEFAULT 0,
      dropped_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_receipts_feedback "
    "ON assistant_feedback_receipts(feedback_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_feedback_events (
      event_id TEXT PRIMARY KEY,
      feedback_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(FEEDBACK_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_feedback_events_feedback "
    "ON assistant_feedback_events(feedback_id, created_at);",
]
