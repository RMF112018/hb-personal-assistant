# 03 — Schema V108 & Contract

New `src/hb_assistant/store/assistant_answer_draft_tables.py` → `V108_STATEMENTS` (5 tables, additive):

- **`assistant_answer_drafts`** — header: `draft_id` PK, `draft_type` (enum), `title`/`objective`/`question`,
  `packet_id` + `packet_type` (enum, denormalized), `answer_contract_digest`, `draft_policy_json`,
  `budget_json`, `status` (enum), `created_by`, `created_at`/`updated_at`, `input_digest`/`output_digest`,
  the 7 counts (`trusted_section_count`/`candidate_section_count`/`caveat_count`/`citation_count`/
  `open_question_count`/`excluded_count`/`section_count`), `truncated`, `metadata_json`. **No answer/response
  field.**
- **`assistant_answer_draft_sections`** — `draft_section_id` PK, `draft_id`, `packet_id`, `packet_item_id`
  (nullable → insufficient_support has none), `section_order`, `section_type` (enum), `heading`,
  **`section_body`** (bounded draft text only — NOT a final answer, NOT operator-approved truth, NOT freeform
  unsupported prose), `review_label`, `effective_state`/`inclusion_state`/`answer_role` (enums), `confidence`,
  `citation_ids_json`, `source_refs_json`, `trusted`/`candidate`/`open_question`/`excluded` (0/1),
  `token_estimate`, `char_count`, `metadata_json`.
- **`assistant_answer_draft_citations`** — `draft_citation_id` PK, `draft_id`, `draft_section_id`, `packet_id`,
  **`packet_citation_id`** (lineage), `citation_order`, `citation_type` (enum), `citation_label`,
  `target_kind`/`target_id`, the 12 provenance anchors + `review_item_id`/`projection_item_id`, **`source_ref`/
  `source_root_key`/`rel_path`** (source-connector carry-through), digests, bounded `evidence_excerpt`/
  `evidence_location`, `confidence`, `review_state`/`effective_state`/`inclusion_state`, `metadata_json`.
  **Provenance CHECK = `packet_citation_id` IS NOT NULL OR ≥1 anchor** (clarification #6).
- **`assistant_answer_draft_receipts`** — reproducibility: digests + counts + `dropped_count` + `truncated`.
- **`assistant_answer_draft_events`** — append-only lifecycle {created, built, exported, marked_stale,
  marked_superseded, failed}. **Lifecycle only — NOT a job/action/workflow table.**

Enums (owned): `draft_type` {trusted_answer_draft, review_aware_answer_draft, implementation_context_draft,
meeting_prep_draft, project_research_draft, open_loop_summary_draft, unknown}; `status` {draft, built, stale,
superseded, failed}; `section_type` {direct_answer, trusted_context, candidate_context, caveat, open_question,
risk, source_summary, implementation_note, excluded_manifest, insufficient_support, unknown}.
`citation_type` + event enums + review/projection/target-kind enums are RE-USED from the N8C-9/10/11 modules
so CHECKs never drift.

Migrator: `LATEST_SCHEMA_VERSION 107 → 108`; `_v108_statements()`; guarded V108 block
(`v108_assistant_answer_draft`) — additive, empty on create, nothing populates on startup, never mutates a
packet/projection/review/source table, generates no final answer, NOT an N8D job schema.
