# 03 — Schema V107 & Table Contract

## Migration
`LATEST_SCHEMA_VERSION 106 → 107` (migrator.py:17). New
`src/hb_assistant/store/assistant_research_packet_tables.py` exports `V107_STATEMENTS`
(`CREATE TABLE/INDEX IF NOT EXISTS`, `_csv` enum CHECKs, shared `_PROVENANCE_COLUMNS`/`_PROVENANCE_CHECK`
≥1 anchor). Migrator: `_v107_statements()` (migrator.py:6996) + guarded V107 block after V106
(migrator.py:8807), migration name `v107_assistant_research_packet` (migrator.py:8810). Additive, empty on
create, nothing populates on startup, research-packet read-product only — NOT graph/bridge/job schema.

## 5 research-packet-owned tables (verified present)
- `assistant_research_packets` — header (packet_id PK, packet_type/status enums, question/objective/scope,
  answer_contract_json, budget_json, input/output/answer_contract digests, trusted/candidate/excluded/
  citation/open-question/item counts, truncated, metadata).
- `assistant_research_packet_items` — one row per considered projection item (12 provenance anchors +
  source/card/target digests, effective_state, inclusion_state, answer_role, bounded title/summary/excerpt,
  included 0/1, exclusion_reason, citation_ids_json). Provenance CHECK ≥1 anchor.
- `assistant_research_packet_citations` — citation manifest (citation_id PK, citation_order, citation_type
  enum, all anchors + review_item_id/projection_item_id + digests, bounded excerpt, evidence_location).
- `assistant_research_packet_receipts` — builder_version, projection_id, digests, budget, counts +
  dropped_count, truncated.
- `assistant_research_packet_events` — append-only lifecycle {created, built, exported, marked_stale,
  marked_superseded, failed}. Lifecycle only — NOT an N8D job/execution event table.

## Enum reuse
target_kind / effective_state / inclusion_state reuse the review/projection enum tuples so CHECKs never
drift. Packet-specific enums: `packet_type`, `status`, `answer_role`, `citation_type`.

## Migration proof (test_research_packet_v107_migration.py, 7 tests, all pass)
Head is 107; 5 tables created; idempotent (double-apply no-op); V100–V106 rows survive; provenance CHECK
rejects an anchorless row.
