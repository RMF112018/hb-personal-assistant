# 03 — Claim Schema & Contract

## Migration (V100)
`LATEST_SCHEMA_VERSION` bumped **99 → 100**. `store/assistant_claim_tables.py::V100_STATEMENTS` is wired
into `store/migrator.py` (`_v100_statements()` + an idempotent apply block guarded by
`SELECT version WHERE version=100`, recorded as `v100_assistant_claims`). Additive only; no existing
table is altered or migrated. Empty on create.

Guard tests updated: `test_source_identity_v99_migration.py` now asserts `LATEST_SCHEMA_VERSION == 100`;
`test_schema_version_head_consistency.py` gains `test_v100_migration_row_present` (the fresh-DB
head==constant and idempotency tests track the constant automatically).

## `assistant_claims`
Columns: `claim_id` (PK, deterministic), `claim_type`, `claim_text`, `normalized_subject/predicate/
object`, provenance (`source_id`, `card_id`, `note_rel_path`, `source_kind`, `source_root_key`,
`source_rel_path`), `evidence_excerpt`, `evidence_location`, `source_state`, `confidence`, `status`,
`review_state`, `extracted_by`, `extractor_version`, `model_name`, `superseded_by`, `created_at`,
`updated_at`, `observed_at`, `valid_from`, `valid_until`, `stale_after`, `metadata_json`.

DB-enforced invariants (CHECK constraints; the repository validates first with clean errors):
- `CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL)` — every claim is **source-backed**.
- `CHECK(length(evidence_excerpt) > 0)` — evidence present (repo also bounds length ≤ 2000).
- `CHECK(confidence BETWEEN 0.0 AND 1.0)`.
- `claim_type` / `status` / `review_state` / `extracted_by` constrained to their enums.
Indexes: `source_id`, `note_rel_path`, `claim_type`, `status`.

Enums: status ∈ {candidate, accepted, rejected, superseded, stale}; review_state ∈ {unreviewed,
auto_accepted, operator_accepted, operator_rejected, not_required}; extracted_by ∈ {rule_based, manual,
future_qwen}.

## `assistant_claim_events`
`event_id` (PK), `claim_id`, `event_type` ∈ {created, updated, accepted, rejected, superseded,
marked_stale, review}, `from_status`, `to_status`, `detail`, `created_at`. Index on `(claim_id, created_at)`.

## Identity
`claim_id = sha256(f"{source_id}|{note_rel_path}|{claim_type}|{claim_text}")[:24]` — deterministic, so
re-extraction upserts rather than duplicates.
