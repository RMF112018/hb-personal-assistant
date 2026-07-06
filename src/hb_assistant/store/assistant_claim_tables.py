"""V100 — Claim Extraction Layer tables (N8C-4).

The first durable memory layer above sources/cards/navigation: atomic, **source-backed** claims
extracted from a source/card/note, plus a lifecycle-event log. Narrow and neutral — NOT a graph
schema. Additive only; no existing table is touched.

Invariants baked into the schema (DB is the backstop; the repository validates first with clean
errors):
  * every claim is source-backed — `CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL)`;
  * evidence is present — `CHECK(length(evidence_excerpt) > 0)` (the repo also bounds its length);
  * confidence is a probability — `CHECK(confidence BETWEEN 0.0 AND 1.0)`;
  * `claim_type` / `status` / `review_state` / `extracted_by` are constrained to known enums.

Tables ship EMPTY; nothing populates them on startup — only an explicit bounded command / service /
test call writes claims.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# A claim is exactly one of these neutral types. Decision/preference/open-loop subsystems are NOT
# built here — for N8C-4 they are simply claim types the extractor can label.
CLAIM_TYPE_VALUES: tuple[str, ...] = (
    "fact",
    "date",
    "risk",
    "assumption",
    "preference",
    "commitment",
    "task_candidate",
    "contradiction_candidate",
    "decision_candidate",
    "unknown",
)

# Lifecycle status of a claim record.
CLAIM_STATUS_VALUES: tuple[str, ...] = (
    "candidate",
    "accepted",
    "rejected",
    "superseded",
    "stale",
)

# Human/operator review disposition.
CLAIM_REVIEW_STATE_VALUES: tuple[str, ...] = (
    "unreviewed",
    "auto_accepted",
    "operator_accepted",
    "operator_rejected",
    "not_required",
)

# Who/what produced the claim. Qwen/Ollama are NOT wired in N8C-4; "future_qwen" is reserved so the
# ingestion seam can accept model output later without a schema change.
CLAIM_EXTRACTED_BY_VALUES: tuple[str, ...] = (
    "rule_based",
    "manual",
    "future_qwen",
)

# Claim lifecycle event kinds.
CLAIM_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "updated",
    "accepted",
    "rejected",
    "superseded",
    "marked_stale",
    "review",
)


V100_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_claims (
      claim_id TEXT PRIMARY KEY,
      claim_type TEXT NOT NULL CHECK(claim_type IN ({_csv(CLAIM_TYPE_VALUES)})),
      claim_text TEXT NOT NULL,
      normalized_subject TEXT,
      normalized_predicate TEXT,
      normalized_object TEXT,
      -- provenance (at least one of source_id / note_rel_path is required)
      source_id TEXT,
      card_id TEXT,
      note_rel_path TEXT,
      source_kind TEXT,
      source_root_key TEXT,
      source_rel_path TEXT,
      evidence_excerpt TEXT NOT NULL,
      evidence_location TEXT,
      source_state TEXT,
      confidence REAL NOT NULL DEFAULT 0.5 CHECK(confidence >= 0.0 AND confidence <= 1.0),
      status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ({_csv(CLAIM_STATUS_VALUES)})),
      review_state TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK(review_state IN ({_csv(CLAIM_REVIEW_STATE_VALUES)})),
      extracted_by TEXT NOT NULL DEFAULT 'rule_based'
        CHECK(extracted_by IN ({_csv(CLAIM_EXTRACTED_BY_VALUES)})),
      extractor_version TEXT,
      model_name TEXT,
      superseded_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      observed_at TEXT,
      valid_from TEXT,
      valid_until TEXT,
      stale_after TEXT,
      metadata_json TEXT,
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL),
      CHECK(length(evidence_excerpt) > 0)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_claims_source ON assistant_claims(source_id);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_claims_note ON assistant_claims(note_rel_path);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_claims_type ON assistant_claims(claim_type);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_claims_status ON assistant_claims(status);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_claim_events (
      event_id TEXT PRIMARY KEY,
      claim_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(CLAIM_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_claim_events_claim ON assistant_claim_events(claim_id, created_at);",
]
