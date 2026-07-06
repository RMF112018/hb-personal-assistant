"""V104 — Decision, Preference, and Open-Loop Memory tables (N8C-8).

Turns the N8C substrate (claims, context-pack items, memory nodes/mentions/compilations) into durable,
advisory, source-backed **decision / preference / open-loop** records an operator/ChatGPT can review:
  * ``assistant_decision_records`` — something was (or appears to have been) decided, or should be
    reviewed as a decision candidate;
  * ``assistant_preference_records`` — a user/system/domain/tool/workflow/communication preference;
  * ``assistant_open_loop_records`` — commitments, task candidates, questions, risks needing follow-up,
    decisions still needed, waiting-fors;
  * ``assistant_decision_memory_events`` — append-only lifecycle log for all three record kinds (NOT a
    bridge/job execution event system — that is N8D, which this slice must not touch or duplicate).

Narrow and advisory. NOT a workflow engine, NOT a task/action executor, NOT a bridge/job schema, NOT a
reminder/scheduler. Additive only; no existing table is touched. Every record defaults to
``status='candidate'`` / ``review_state='unreviewed'`` — nothing is auto-accepted, and identifying a
record NEVER accepts the underlying claim (candidate claims stay candidate/unreviewed). The
``accepted``/``open``/``closed``/``operator_*`` statuses are enum values RESERVED for a future operator-
disposition slice — N8C-8 implements only creation, explicit stale, and lineage-scoped supersede.

Invariants baked into the schema (DB is the backstop; the models validate first with clean errors):
  * every record is provenance-backed — a table CHECK requires at least one anchor
    (source_id / note_rel_path / claim_id / memory_node_id / memory_mention_id / compilation_id /
    pack_id / pack_item_id / receipt_id);
  * types / statuses / review_state / strength / priority / event kinds are enum-constrained;
  * confidence is 0..1; text columns store only BOUNDED excerpts (the models cap them before write) —
    never a raw source body, raw email body, or raw prompt/response.

All four tables ship EMPTY; nothing populates them on startup — only an explicit bounded
``decision-memory extract --apply`` command / service call writes rows. No lifespan / scheduler /
watcher / worker path extracts records.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# Kind of decision record.
DECISION_TYPE_VALUES: tuple[str, ...] = (
    "decision",
    "decision_candidate",
    "policy",
    "architecture_decision",
    "operator_preference_decision",
    "unknown",
)

# Kind of preference record.
PREFERENCE_TYPE_VALUES: tuple[str, ...] = (
    "user_preference",
    "system_preference",
    "domain_preference",
    "workflow_preference",
    "tool_preference",
    "communication_preference",
    "unknown",
)

# Kind of open-loop record.
OPEN_LOOP_TYPE_VALUES: tuple[str, ...] = (
    "commitment",
    "task_candidate",
    "question",
    "risk_followup",
    "decision_needed",
    "waiting_for",
    "unknown",
)

# Decision / preference lifecycle. `accepted`/`rejected` reserved for a future disposition slice
# (N8C-8 uses only candidate/superseded/stale).
DECISION_STATUS_VALUES: tuple[str, ...] = (
    "candidate",
    "accepted",
    "rejected",
    "superseded",
    "stale",
)

# Open-loop lifecycle. `open`/`closed`/`rejected` reserved for a future disposition slice (N8C-8 uses
# only candidate/superseded/stale).
OPEN_LOOP_STATUS_VALUES: tuple[str, ...] = (
    "candidate",
    "open",
    "closed",
    "rejected",
    "stale",
    "superseded",
)

# Advisory review state — DISTINCT from a claim disposition. `operator_*` reserved for a future slice.
DECISION_REVIEW_STATE_VALUES: tuple[str, ...] = (
    "unreviewed",
    "needs_review",
    "operator_accepted",
    "operator_rejected",
    "not_required",
)

# Preference strength (advisory).
PREFERENCE_STRENGTH_VALUES: tuple[str, ...] = (
    "weak",
    "medium",
    "strong",
    "explicit",
)

# Open-loop priority (advisory).
OPEN_LOOP_PRIORITY_VALUES: tuple[str, ...] = (
    "low",
    "medium",
    "high",
    "unknown",
)

# Which record kind an event belongs to.
DECISION_MEMORY_RECORD_KIND_VALUES: tuple[str, ...] = (
    "decision",
    "preference",
    "open_loop",
)

# Lifecycle event kinds — LIFECYCLE ONLY (not a bridge/job execution event system). `closed`/`reopened`
# are enum values reserved for a future open-loop disposition slice.
DECISION_MEMORY_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "updated",
    "marked_stale",
    "closed",
    "reopened",
    "superseded",
    "rejected",
    "failed",
)


# Shared provenance + CHECK fragment (at least one anchor). Kept as a constant so the three record
# tables stay identical and the "provenance required" invariant can't drift between them.
_PROVENANCE_COLUMNS = """
      source_id TEXT,
      note_rel_path TEXT,
      claim_id TEXT,
      memory_node_id TEXT,
      memory_mention_id TEXT,
      compilation_id TEXT,
      pack_id TEXT,
      pack_item_id TEXT,
      receipt_id TEXT,
      evidence_excerpt TEXT,
      evidence_location TEXT,
      source_digest TEXT,
      card_digest TEXT,
"""

_PROVENANCE_CHECK = """
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL OR claim_id IS NOT NULL
            OR memory_node_id IS NOT NULL OR memory_mention_id IS NOT NULL
            OR compilation_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL
            OR receipt_id IS NOT NULL)
"""


V104_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_decision_records (
      decision_id TEXT PRIMARY KEY,
      identity_key TEXT NOT NULL,
      decision_type TEXT NOT NULL CHECK(decision_type IN ({_csv(DECISION_TYPE_VALUES)})),
      decision_text TEXT,
      normalized_subject TEXT,
      normalized_decision TEXT,
      domain TEXT,
      status TEXT NOT NULL DEFAULT 'candidate'
        CHECK(status IN ({_csv(DECISION_STATUS_VALUES)})),
      review_state TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK(review_state IN ({_csv(DECISION_REVIEW_STATE_VALUES)})),
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
{_PROVENANCE_COLUMNS}      observed_at TEXT,
      decided_at TEXT,
      valid_from TEXT,
      valid_until TEXT,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
{_PROVENANCE_CHECK}    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_decision_records_identity "
    "ON assistant_decision_records(identity_key, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_decision_records_type "
    "ON assistant_decision_records(decision_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_decision_records_source "
    "ON assistant_decision_records(source_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_preference_records (
      preference_id TEXT PRIMARY KEY,
      identity_key TEXT NOT NULL,
      preference_type TEXT NOT NULL CHECK(preference_type IN ({_csv(PREFERENCE_TYPE_VALUES)})),
      preference_text TEXT,
      normalized_subject TEXT,
      normalized_preference TEXT,
      domain TEXT,
      strength TEXT CHECK(strength IS NULL OR strength IN ({_csv(PREFERENCE_STRENGTH_VALUES)})),
      status TEXT NOT NULL DEFAULT 'candidate'
        CHECK(status IN ({_csv(DECISION_STATUS_VALUES)})),
      review_state TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK(review_state IN ({_csv(DECISION_REVIEW_STATE_VALUES)})),
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
{_PROVENANCE_COLUMNS}      observed_at TEXT,
      valid_from TEXT,
      valid_until TEXT,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
{_PROVENANCE_CHECK}    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_preference_records_identity "
    "ON assistant_preference_records(identity_key, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_preference_records_type "
    "ON assistant_preference_records(preference_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_preference_records_source "
    "ON assistant_preference_records(source_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_open_loop_records (
      open_loop_id TEXT PRIMARY KEY,
      identity_key TEXT NOT NULL,
      open_loop_type TEXT NOT NULL CHECK(open_loop_type IN ({_csv(OPEN_LOOP_TYPE_VALUES)})),
      open_loop_text TEXT,
      normalized_subject TEXT,
      normalized_action TEXT,
      domain TEXT,
      status TEXT NOT NULL DEFAULT 'candidate'
        CHECK(status IN ({_csv(OPEN_LOOP_STATUS_VALUES)})),
      review_state TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK(review_state IN ({_csv(DECISION_REVIEW_STATE_VALUES)})),
      priority TEXT CHECK(priority IS NULL OR priority IN ({_csv(OPEN_LOOP_PRIORITY_VALUES)})),
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
{_PROVENANCE_COLUMNS}      observed_at TEXT,
      due_at TEXT,
      stale_after TEXT,
      owner_hint TEXT,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
{_PROVENANCE_CHECK}    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_open_loop_records_identity "
    "ON assistant_open_loop_records(identity_key, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_open_loop_records_type "
    "ON assistant_open_loop_records(open_loop_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_open_loop_records_source "
    "ON assistant_open_loop_records(source_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_decision_memory_events (
      event_id TEXT PRIMARY KEY,
      record_kind TEXT NOT NULL CHECK(record_kind IN ({_csv(DECISION_MEMORY_RECORD_KIND_VALUES)})),
      record_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(DECISION_MEMORY_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_decision_memory_events_record "
    "ON assistant_decision_memory_events(record_kind, record_id, created_at);",
]
