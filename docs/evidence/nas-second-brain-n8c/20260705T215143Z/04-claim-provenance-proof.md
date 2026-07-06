# 04 — Claim Provenance Proof

Every claim is source-backed; unsupported claims are refused; evidence is bounded; confidence/status/
review are constrained. Source: `tests/test_claim_repository.py` (12 tests, all pass).

## Provenance is mandatory
- `test_unsupported_batch_rejected` — `ingest_candidates` with neither `source_id` nor `note_rel_path`
  raises `ClaimValidationError` (nothing written). No trusted unsupported claims.
- DB backstop: a direct `INSERT` with no source anchor fails the
  `CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL)` (proven in the migration smoke).
- `test_ingest_with_source_provenance` / `test_note_only_provenance_ok` — a claim persists its full
  provenance (`source_id`, `card_id`, `note_rel_path`, `source_kind`, `source_root_key`,
  `source_rel_path`, `extractor_version`) and computes the deterministic `claim_id`. A note anchor
  alone is sufficient.

## Field validation & bounds
- `test_bad_candidate_collected_not_written` — invalid claim_type / empty text land in `rejected`, the
  rest are written.
- `test_confidence_is_clamped` + `test_db_check_blocks_out_of_range_confidence` — the repo clamps
  confidence into [0,1]; a direct bad write is rejected by the CHECK.
- `test_invalid_status_and_review_rejected` — bad `status`/`review_state` raise.
- `test_evidence_is_bounded` — a 6000-char evidence is stored ≤ `EVIDENCE_MAX_CHARS` (2000).

## Lifecycle
- `test_reingest_is_idempotent_and_logs_events` — re-ingest updates (not duplicates); a `created` then
  `updated` event is logged.
- `test_set_status_and_mark_stale` — status/review transitions logged as `accepted` / `marked_stale`
  events.

## Write isolation
`claim_repository.py` issues only `INSERT INTO assistant_claims`, `INSERT INTO assistant_claim_events`,
`UPDATE assistant_claims` — no source/import/raw table is written (grep-verified).
