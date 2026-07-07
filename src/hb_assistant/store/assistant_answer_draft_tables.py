"""V108 — Citation-Safe Answer Drafts (N8C-14).

Durable, bounded, citation-safe **draft** read products materialized from the N8C-11 research packets
(``assistant_research_packet*``). They turn a packet + its answer-context contract into a bounded set of cited
DRAFT sections a downstream consumer (ChatGPT / frontend / a future N8D job) can read — cited sections that
preserve review labels, source provenance, excluded-content rules, and the packet's no-execution policy —
WITHOUT producing a final authoritative answer and WITHOUT mutating any source / review / projection / packet
record.

  * ``assistant_answer_drafts`` — draft headers (type, question/objective, packet lineage, answer-contract
    digest, policy, budget, digests, per-kind counts). There is deliberately NO ``final_answer`` /
    ``answer_text`` / ``generated_answer`` / ``authoritative_answer`` / ``operator_approved_answer`` field
    anywhere: a draft is guidance, never final truth.
  * ``assistant_answer_draft_sections`` — bounded DRAFT sections derived from packet items, each mapped to a
    ``section_type`` (direct_answer / trusted_context / candidate_context / caveat / open_question /
    excluded_manifest / insufficient_support / …). ``section_body`` is BOUNDED draft section text only — a
    restatement assembled solely from the packet item's own bounded title/summary/evidence_excerpt + review
    label; it is NOT a final answer, NOT operator-approved truth, and NOT freeform unsupported prose. Sections
    never store a raw source/card/vault body, a raw email body, a full packet payload, or a raw
    prompt/response.
  * ``assistant_answer_draft_citations`` — the draft citation manifest: bounded, provenance-anchored citations
    backing draft sections. Each citation preserves its originating ``packet_citation_id`` when available; a
    citation MUST carry that packet-citation lineage OR at least one provenance anchor (enforced by a table
    CHECK AND by model validation). Citations may additionally carry read-only source-connector metadata
    (``source_ref`` / ``source_root_key`` / ``rel_path``) — indexed metadata only, never a live file read.
  * ``assistant_answer_draft_receipts`` — build receipts proving reproducibility + budget/citation accounting
    (input/output/answer-contract digests, counts, dropped/truncated).
  * ``assistant_answer_draft_events`` — append-only lifecycle log (created / built / exported / marked_stale /
    marked_superseded / failed). LIFECYCLE ONLY — NOT a bridge/job/action/workflow execution event system
    (that is N8D, which this slice must not touch or duplicate).

Narrow and draft-owned. NOT a graph schema, NOT a workflow/bridge/job schema, NOT a task/action executor, NOT
a final-answer generator. An answer draft is a materialized read product, never source truth: it NEVER
converts a candidate record into accepted truth, NEVER turns an open loop into an executable instruction,
NEVER fabricates a direct answer when the packet's ``answer_contract`` withholds one, and effective/review
state is READ (as already frozen into the packet items/citations it consumes), never written back. Additive
only; no existing table is touched. All five tables ship EMPTY; nothing populates them on startup — only an
explicit bounded ``answer-draft build --apply`` command / service call writes rows. No lifespan / scheduler /
watcher / worker path builds drafts.
"""

from __future__ import annotations

from hb_assistant.store.assistant_intelligence_projection_tables import (
    INCLUSION_STATE_VALUES,
)
from hb_assistant.store.assistant_research_packet_tables import (
    ANSWER_ROLE_VALUES,
    CITATION_TYPE_VALUES,
    PACKET_EVENT_TYPE_VALUES,
    PACKET_TYPE_VALUES,
)
from hb_assistant.store.assistant_review_tables import (
    EFFECTIVE_STATE_VALUES,
    REVIEW_STATE_VALUES,
    REVIEW_TARGET_KIND_VALUES,
)


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What kind of answer DRAFT this is (defines the default inclusion/section policy). Distinct from a packet
# type — a draft is the citation-safe read product built from ONE packet.
DRAFT_TYPE_VALUES: tuple[str, ...] = (
    "trusted_answer_draft",
    "review_aware_answer_draft",
    "implementation_context_draft",
    "meeting_prep_draft",
    "project_research_draft",
    "open_loop_summary_draft",
    "unknown",
)

# Draft lifecycle.
DRAFT_STATUS_VALUES: tuple[str, ...] = (
    "draft",
    "built",
    "stale",
    "superseded",
    "failed",
)

# How each draft section participates in the citation-safe draft. ``insufficient_support`` is the ONLY section
# emitted when the packet's answer_contract withholds an answer (answer_allowed=False) — never a fabricated
# ``direct_answer``.
SECTION_TYPE_VALUES: tuple[str, ...] = (
    "direct_answer",
    "trusted_context",
    "candidate_context",
    "caveat",
    "open_question",
    "risk",
    "source_summary",
    "implementation_note",
    "excluded_manifest",
    "insufficient_support",
    "unknown",
)

# Citation-type + lifecycle-event enums are RE-USED from the N8C-11 packet schema so the draft layer can never
# drift from the packets it reads. Effective/review/inclusion/target-kind enums come from the N8C-9 review +
# N8C-10 projection schemas for the same reason. packet_type is re-used to constrain the denormalized copy.
_CITATION_TYPES = CITATION_TYPE_VALUES
_EVENT_TYPES = PACKET_EVENT_TYPE_VALUES
_PACKET_TYPES = PACKET_TYPE_VALUES
_TARGET_KINDS = REVIEW_TARGET_KIND_VALUES
_REVIEW_STATES = REVIEW_STATE_VALUES
_EFFECTIVE_STATES = EFFECTIVE_STATE_VALUES
_INCLUSION_STATES = INCLUSION_STATE_VALUES
# A section carries the originating packet-item answer_role (re-used tuple so it can never drift).
_ANSWER_ROLES = ANSWER_ROLE_VALUES


# Shared provenance columns (the 12 upstream anchors) — used by the draft-citations table so every citation
# can be traced to a concrete source record even when its originating packet_citation_id is absent.
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

# Citation provenance CHECK — the 12 upstream anchors PLUS review_item_id / projection_item_id PLUS the
# originating packet_citation_id. A draft citation is valid if it preserves its packet-citation lineage OR
# carries at least one provenance anchor (clarification #6: preserve packet_citation_id whenever available;
# otherwise require ≥1 anchor and mark lineage degraded in metadata).
_CITATION_PROVENANCE_CHECK = """
      CHECK(packet_citation_id IS NOT NULL
            OR source_id IS NOT NULL OR note_rel_path IS NOT NULL OR claim_id IS NOT NULL
            OR receipt_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL
            OR memory_node_id IS NOT NULL OR memory_mention_id IS NOT NULL
            OR compilation_id IS NOT NULL OR decision_id IS NOT NULL
            OR preference_id IS NOT NULL OR open_loop_id IS NOT NULL
            OR review_item_id IS NOT NULL OR projection_item_id IS NOT NULL)
"""


V108_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_answer_drafts (
      draft_id TEXT PRIMARY KEY,
      draft_type TEXT NOT NULL CHECK(draft_type IN ({_csv(DRAFT_TYPE_VALUES)})),
      title TEXT,
      objective TEXT,
      question TEXT,
      packet_id TEXT,
      packet_type TEXT CHECK(packet_type IS NULL OR packet_type IN ({_csv(_PACKET_TYPES)})),
      answer_contract_digest TEXT,
      draft_policy_json TEXT,
      budget_json TEXT,
      status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ({_csv(DRAFT_STATUS_VALUES)})),
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      input_digest TEXT,
      output_digest TEXT,
      trusted_section_count INTEGER NOT NULL DEFAULT 0,
      candidate_section_count INTEGER NOT NULL DEFAULT 0,
      caveat_count INTEGER NOT NULL DEFAULT 0,
      citation_count INTEGER NOT NULL DEFAULT 0,
      open_question_count INTEGER NOT NULL DEFAULT 0,
      excluded_count INTEGER NOT NULL DEFAULT 0,
      section_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_drafts_type "
    "ON assistant_answer_drafts(draft_type, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_drafts_packet "
    "ON assistant_answer_drafts(packet_id);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_drafts_input "
    "ON assistant_answer_drafts(input_digest);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_answer_draft_sections (
      draft_section_id TEXT PRIMARY KEY,
      draft_id TEXT NOT NULL,
      packet_id TEXT,
      packet_item_id TEXT,
      section_order INTEGER NOT NULL DEFAULT 0,
      section_type TEXT NOT NULL CHECK(section_type IN ({_csv(SECTION_TYPE_VALUES)})),
      heading TEXT,
      section_body TEXT,
      review_label TEXT,
      effective_state TEXT CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      inclusion_state TEXT CHECK(inclusion_state IS NULL OR inclusion_state IN ({_csv(_INCLUSION_STATES)})),
      answer_role TEXT CHECK(answer_role IS NULL OR answer_role IN ({_csv(_ANSWER_ROLES)})),
      confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
      citation_ids_json TEXT,
      source_refs_json TEXT,
      trusted INTEGER NOT NULL DEFAULT 0 CHECK(trusted IN (0, 1)),
      candidate INTEGER NOT NULL DEFAULT 0 CHECK(candidate IN (0, 1)),
      open_question INTEGER NOT NULL DEFAULT 0 CHECK(open_question IN (0, 1)),
      excluded INTEGER NOT NULL DEFAULT 0 CHECK(excluded IN (0, 1)),
      token_estimate INTEGER NOT NULL DEFAULT 0,
      char_count INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_sections_draft "
    "ON assistant_answer_draft_sections(draft_id, section_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_sections_type "
    "ON assistant_answer_draft_sections(draft_id, section_type);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_sections_item "
    "ON assistant_answer_draft_sections(packet_item_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_answer_draft_citations (
      draft_citation_id TEXT PRIMARY KEY,
      draft_id TEXT NOT NULL,
      draft_section_id TEXT NOT NULL,
      packet_id TEXT,
      packet_citation_id TEXT,
      citation_order INTEGER NOT NULL DEFAULT 0,
      citation_type TEXT NOT NULL CHECK(citation_type IN ({_csv(_CITATION_TYPES)})),
      citation_label TEXT,
      target_kind TEXT CHECK(target_kind IS NULL OR target_kind IN ({_csv(_TARGET_KINDS)})),
      target_id TEXT,
{_PROVENANCE_COLUMNS}      review_item_id TEXT,
      projection_item_id TEXT,
      source_ref TEXT,
      source_root_key TEXT,
      rel_path TEXT,
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
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_citations_draft "
    "ON assistant_answer_draft_citations(draft_id, citation_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_citations_section "
    "ON assistant_answer_draft_citations(draft_section_id, citation_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_citations_packet_citation "
    "ON assistant_answer_draft_citations(packet_citation_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_answer_draft_receipts (
      draft_receipt_id TEXT PRIMARY KEY,
      draft_id TEXT NOT NULL,
      builder_version TEXT,
      packet_id TEXT,
      input_digest TEXT,
      output_digest TEXT,
      answer_contract_digest TEXT,
      draft_policy_json TEXT,
      budget_json TEXT,
      trusted_section_count INTEGER NOT NULL DEFAULT 0,
      candidate_section_count INTEGER NOT NULL DEFAULT 0,
      caveat_count INTEGER NOT NULL DEFAULT 0,
      citation_count INTEGER NOT NULL DEFAULT 0,
      open_question_count INTEGER NOT NULL DEFAULT 0,
      excluded_count INTEGER NOT NULL DEFAULT 0,
      section_count INTEGER NOT NULL DEFAULT 0,
      dropped_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_receipts_draft "
    "ON assistant_answer_draft_receipts(draft_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_answer_draft_events (
      event_id TEXT PRIMARY KEY,
      draft_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(_EVENT_TYPES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_answer_draft_events_draft "
    "ON assistant_answer_draft_events(draft_id, created_at);",
]
