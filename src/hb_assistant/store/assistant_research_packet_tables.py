"""V107 — Review-Aware Research Packets, Citation Manifests & Answer-Context Contracts (N8C-11).

Durable, bounded, review-aware **read products** materialized from the N8C-10 intelligence projections
(``assistant_intelligence_projection*``). They let a downstream consumer (ChatGPT / frontend / a future N8D
job) ask "for this question/objective, which projection items are answer-support, which citations back each
answerable claim, what may be stated as trusted vs must be labelled candidate vs must be excluded, and what
open questions remain" — WITHOUT rehydrating raw source/card/vault/email bodies, WITHOUT generating a final
answer, and WITHOUT mutating any source / review / projection record.

  * ``assistant_research_packets`` — packet headers (type, question/objective, scope, answer-context
    contract, budget, projection lineage, digests, per-role counts). ``answer_contract_json`` is guidance
    METADATA only — it is NOT generated answer content and carries no answer prose.
  * ``assistant_research_packet_items`` — bounded items selected from N8C-10 projection items, each mapped to
    an ``answer_role`` (primary_support / candidate_context / excluded_context / open_question / …). Items
    store only BOUNDED excerpts + ids/digests/state/role — never a raw source/card/vault body, a raw email
    body, a full enrichment ``result_json``, a full context-pack/projection export, a full review-item
    payload, a full memory compilation, or a raw prompt/response. Excluded (``included=0``) items keep target
    ids / effective state / exclusion reason / digests but carry no unnecessary content.
  * ``assistant_research_packet_citations`` — the citation manifest: bounded, provenance-anchored citations
    backing packet items. Each citation MUST carry at least one provenance anchor (enforced by a table CHECK
    AND by model validation). Citation ids fold anchor-specific entropy so two citations for the same
    target/digest never collide.
  * ``assistant_research_packet_receipts`` — build receipts proving reproducibility + budget/filter/citation
    accounting (input/output/answer-contract digests, counts, dropped/truncated).
  * ``assistant_research_packet_events`` — append-only lifecycle log (created / built / exported /
    marked_stale / marked_superseded / failed). LIFECYCLE ONLY — NOT a bridge/job execution event system
    (that is N8D, which this slice must not touch or duplicate).

Narrow and packet-owned. NOT a graph schema, NOT a workflow/bridge/job schema, NOT a task executor, NOT an
answer generator. A research packet is a materialized read product, never source truth: it NEVER converts a
candidate record into accepted truth, NEVER turns an open loop into an executable instruction, and effective
state is READ (as already frozen into the N8C-10 projection items), never written back. Additive only; no
existing table is touched. All five tables ship EMPTY; nothing populates them on startup — only an explicit
bounded ``research-packet build --apply`` command / service call writes rows. No lifespan / scheduler /
watcher / worker path builds packets.
"""

from __future__ import annotations

from hb_assistant.store.assistant_intelligence_projection_tables import (
    INCLUSION_STATE_VALUES,
)
from hb_assistant.store.assistant_review_tables import (
    EFFECTIVE_STATE_VALUES,
    REVIEW_STATE_VALUES,
    REVIEW_TARGET_KIND_VALUES,
)


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What kind of answer-context packet this is (defines the default inclusion/answer policy).
PACKET_TYPE_VALUES: tuple[str, ...] = (
    "trusted_answer_context",
    "review_aware_answer_context",
    "implementation_research_context",
    "project_research_context",
    "decision_research_context",
    "open_loop_research_context",
    "meeting_prep_context",
    "unknown",
)

# Packet lifecycle.
PACKET_STATUS_VALUES: tuple[str, ...] = (
    "draft",
    "built",
    "stale",
    "superseded",
    "failed",
)

# How each packet item participates in a future answer (derived from its inclusion state + the policy).
ANSWER_ROLE_VALUES: tuple[str, ...] = (
    "primary_support",
    "supporting_context",
    "candidate_context",
    "counterpoint",
    "excluded_context",
    "open_question",
    "risk_or_caveat",
    "implementation_note",
    "unknown",
)

# What a citation points at.
CITATION_TYPE_VALUES: tuple[str, ...] = (
    "source",
    "claim",
    "context_pack_item",
    "memory",
    "decision",
    "preference",
    "open_loop",
    "review_item",
    "projection_item",
    "unknown",
)

# Packet lifecycle event kinds — LIFECYCLE ONLY (not a bridge/job execution event system).
PACKET_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "built",
    "exported",
    "marked_stale",
    "marked_superseded",
    "failed",
)

# Effective/review/inclusion/target-kind enums are re-used from the N8C-9 review + N8C-10 projection schemas
# so the packet layer can never drift from the projections it reads.
_TARGET_KINDS = REVIEW_TARGET_KIND_VALUES
_REVIEW_STATES = REVIEW_STATE_VALUES
_EFFECTIVE_STATES = EFFECTIVE_STATE_VALUES
_INCLUSION_STATES = INCLUSION_STATE_VALUES


# Shared provenance columns + CHECK (at least one anchor) — used by BOTH the packet-items table and the
# citations table, so every item and every citation can always be traced back to a concrete source record.
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
"""

# Item provenance anchor set (12 upstream anchors). target_id is separately NOT NULL.
_ITEM_PROVENANCE_CHECK = """
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL OR claim_id IS NOT NULL
            OR receipt_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL
            OR memory_node_id IS NOT NULL OR memory_mention_id IS NOT NULL
            OR compilation_id IS NOT NULL OR decision_id IS NOT NULL
            OR preference_id IS NOT NULL OR open_loop_id IS NOT NULL)
"""

# Citation provenance anchor set — the 12 upstream anchors PLUS review_item_id / projection_item_id, so a
# citation that points only at a review item or a projection item still satisfies the anchor requirement.
_CITATION_PROVENANCE_CHECK = """
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL OR claim_id IS NOT NULL
            OR receipt_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL
            OR memory_node_id IS NOT NULL OR memory_mention_id IS NOT NULL
            OR compilation_id IS NOT NULL OR decision_id IS NOT NULL
            OR preference_id IS NOT NULL OR open_loop_id IS NOT NULL
            OR review_item_id IS NOT NULL OR projection_item_id IS NOT NULL)
"""


V107_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_research_packets (
      packet_id TEXT PRIMARY KEY,
      packet_type TEXT NOT NULL CHECK(packet_type IN ({_csv(PACKET_TYPE_VALUES)})),
      title TEXT,
      objective TEXT,
      question TEXT,
      scope_json TEXT,
      answer_contract_json TEXT,
      budget_json TEXT,
      status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ({_csv(PACKET_STATUS_VALUES)})),
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      projection_id TEXT,
      input_digest TEXT,
      output_digest TEXT,
      answer_contract_digest TEXT,
      trusted_count INTEGER NOT NULL DEFAULT 0,
      candidate_count INTEGER NOT NULL DEFAULT 0,
      excluded_count INTEGER NOT NULL DEFAULT 0,
      citation_count INTEGER NOT NULL DEFAULT 0,
      open_question_count INTEGER NOT NULL DEFAULT 0,
      item_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packets_type "
    "ON assistant_research_packets(packet_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packets_projection "
    "ON assistant_research_packets(projection_id);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packets_input "
    "ON assistant_research_packets(input_digest);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_research_packet_items (
      packet_item_id TEXT PRIMARY KEY,
      packet_id TEXT NOT NULL,
      projection_id TEXT,
      projection_item_id TEXT,
      item_order INTEGER NOT NULL DEFAULT 0,
      target_kind TEXT NOT NULL CHECK(target_kind IN ({_csv(_TARGET_KINDS)})),
      target_id TEXT NOT NULL,
      review_item_id TEXT,
      effective_state TEXT CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      inclusion_state TEXT CHECK(inclusion_state IS NULL OR inclusion_state IN ({_csv(_INCLUSION_STATES)})),
      answer_role TEXT NOT NULL CHECK(answer_role IN ({_csv(ANSWER_ROLE_VALUES)})),
      title TEXT,
      summary TEXT,
      evidence_excerpt TEXT,
{_PROVENANCE_COLUMNS}      source_digest TEXT,
      card_digest TEXT,
      target_digest TEXT,
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      priority TEXT,
      token_estimate INTEGER NOT NULL DEFAULT 0,
      included INTEGER NOT NULL DEFAULT 0 CHECK(included IN (0, 1)),
      exclusion_reason TEXT,
      citation_ids_json TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
{_ITEM_PROVENANCE_CHECK}    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packet_items_packet "
    "ON assistant_research_packet_items(packet_id, item_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packet_items_role "
    "ON assistant_research_packet_items(packet_id, answer_role);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packet_items_target "
    "ON assistant_research_packet_items(target_kind, target_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_research_packet_citations (
      citation_id TEXT PRIMARY KEY,
      packet_id TEXT NOT NULL,
      packet_item_id TEXT NOT NULL,
      citation_order INTEGER NOT NULL DEFAULT 0,
      citation_type TEXT NOT NULL CHECK(citation_type IN ({_csv(CITATION_TYPE_VALUES)})),
      label TEXT,
      target_kind TEXT CHECK(target_kind IS NULL OR target_kind IN ({_csv(_TARGET_KINDS)})),
      target_id TEXT,
{_PROVENANCE_COLUMNS}      review_item_id TEXT,
      projection_item_id TEXT,
      source_digest TEXT,
      card_digest TEXT,
      target_digest TEXT,
      evidence_excerpt TEXT,
      evidence_location TEXT,
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      review_state TEXT CHECK(review_state IS NULL OR review_state IN ({_csv(_REVIEW_STATES)})),
      effective_state TEXT CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      inclusion_state TEXT CHECK(inclusion_state IS NULL OR inclusion_state IN ({_csv(_INCLUSION_STATES)})),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT,
{_CITATION_PROVENANCE_CHECK}    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packet_citations_packet "
    "ON assistant_research_packet_citations(packet_id, citation_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packet_citations_item "
    "ON assistant_research_packet_citations(packet_item_id, citation_order);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_research_packet_receipts (
      packet_receipt_id TEXT PRIMARY KEY,
      packet_id TEXT NOT NULL,
      builder_version TEXT,
      projection_id TEXT,
      input_digest TEXT,
      output_digest TEXT,
      answer_contract_digest TEXT,
      budget_json TEXT,
      trusted_count INTEGER NOT NULL DEFAULT 0,
      candidate_count INTEGER NOT NULL DEFAULT 0,
      excluded_count INTEGER NOT NULL DEFAULT 0,
      citation_count INTEGER NOT NULL DEFAULT 0,
      open_question_count INTEGER NOT NULL DEFAULT 0,
      dropped_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packet_receipts_packet "
    "ON assistant_research_packet_receipts(packet_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_research_packet_events (
      event_id TEXT PRIMARY KEY,
      packet_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(PACKET_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_research_packet_events_packet "
    "ON assistant_research_packet_events(packet_id, created_at);",
]
