# N8C-7 — V103 schema & memory contract

## Migration
- New head: **`LATEST_SCHEMA_VERSION = 103`**. Migration name `v103_assistant_memory`.
- Wiring mirrors V102 exactly: `_v103_statements()` staticmethod + a `WHERE version = 103` guarded
  insert block after the V102 block; head bumped 102 → 103.
- Additive + idempotent: applying twice leaves exactly one v103 row (proof:
  `test_memory_v103_migration.py::test_migration_is_idempotent_applied_twice`).
- Prior V100 (`assistant_claims`), V101 (`assistant_enrichment_*`), V102 (`assistant_context_pack_*`)
  migration rows and tables survive V103 (proof:
  `test_memory_v103_migration.py::test_prior_v100_v101_v102_rows_remain`,
  `test_schema_version_head_consistency.py::test_prior_assistant_tables_survive_v103`).

## Four memory-owned tables (`store/assistant_memory_tables.py`, `V103_STATEMENTS`, 9 indexes)
All TEXT PKs, `created_at`/`updated_at DEFAULT CURRENT_TIMESTAMP`, `*_json` bounded, **no FKs**; enum
tuples in the module are the single source of truth for the DB `CHECK` constraints and the Python layer.

1. **`assistant_memory_nodes`** — canonical objects. `node_id` PK; `node_type` CHECK
   (entity/concept/domain/project/person/organization/place/asset/topic/preference_area/risk_area/unknown);
   `canonical_name`, `normalized_name`, `aliases_json`, `domain`; `status` CHECK
   (active/stale/superseded/merged/archived); `review_tier` CHECK; `confidence` 0..1;
   `source_count`/`claim_count`/`mention_count`/`compilation_count` (≥0); `input_digest`, `created_by`,
   `metadata_json`.
2. **`assistant_memory_mentions`** — source-backed evidence. `mention_id` PK; `node_id`; `mention_type`
   CHECK (claim_subject/claim_object/source_title/context_pack_item/enrichment_summary/backlink_target/
   manual_seed/unknown); `mention_text`; provenance anchors
   `source_id/note_rel_path/claim_id/job_id/receipt_id/pack_id/pack_item_id`; bounded `evidence_excerpt`;
   `source_digest/card_digest`; `confidence`; `review_tier`; `source_state`; `metadata_json`.
   **Table CHECK requires ≥1 provenance anchor** (`source_id IS NOT NULL OR note_rel_path IS NOT NULL OR
   claim_id IS NOT NULL OR receipt_id IS NOT NULL OR pack_id IS NOT NULL OR pack_item_id IS NOT NULL`) —
   no floating mention can exist (proof: `test_memory_repository.py::test_mention_requires_provenance`).
3. **`assistant_memory_compilations`** — bounded summaries. `compilation_id` PK; `node_id`;
   `compile_type` CHECK (node_summary/domain_summary/project_summary/topic_summary/review_packet);
   bounded `summary`; `key_points_json/open_questions_json/risks_json/preferences_json`; counts;
   `input_digest/output_digest`; `stale_count`; `truncated`; `status` CHECK
   (built/stale/superseded/failed); `created_by`, `metadata_json`.
4. **`assistant_memory_events`** — append-only **lifecycle only**
   (created/updated/compiled/marked_stale/merged/archived/failed). Not a bridge/job/agent event log.

## Deterministic identity (idempotency contract)
- `node_id  = sha256(node_type | normalized_name | domain)[:24]` — stable while normalized identity is
  unchanged (`test_memory_repository.py::test_node_id_determinism`,
  `test_memory_compiler.py::test_node_id_stable_when_identity_unchanged`).
- `mention_id = sha256(node_id | source_id | claim_id | pack_item_id | mention_type | mention_text)[:24]`
  — same anchor → no duplicate (`test_memory_repository.py::test_upsert_mention_idempotent`).
- `compilation_id = sha256(node_id | compile_type | input_digest | compiler_version)[:24]` — a **changed
  input digest yields a new compilation** and the prior `built` compilation for that `(node,
  compile_type)` is marked `superseded`
  (`test_memory_repository.py::test_persist_compilation_supersede_on_new_input`,
  `test_memory_compiler.py::test_changed_input_creates_new_compilation_and_supersedes`).
- `COMPILER_VERSION = "memory-compiler-v1"` folded into `compilation_id`.

## Advisory review tier (provenance quality — NEVER a claim disposition)
`mention_tier()` order: ambiguous card link → `ambiguous_source`; deleted/missing/stale source →
`stale_source`; Qwen-derived `enrichment_summary` → `needs_operator_review`; `backlink_target` →
`low_confidence`; raw `claim_text` fallback → `needs_operator_review`; confidence <0.4 →
`low_confidence`; deterministic source-backed claim subject/object → `trusted_source_backed`; else
`candidate_only`. A node inherits its **worst (most-cautious)** mention tier (`worst_tier()`).
Node `status` / `review_tier` / a compilation NEVER imply a claim was accepted — the compiler only READS
claims.
