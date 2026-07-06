# V101 Schema + Contract

`store/assistant_enrichment_tables.py` — `V101_STATEMENTS` (additive, `IF NOT EXISTS`, idempotent).

`assistant_enrichment_jobs`: job_id (PK, deterministic 24-hex), job_type/subject_type/status enums
(CHECK), provenance `CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL)`, priority>=0,
payload_json, source_digest/card_digest/input_digest, lease_owner/lease_expires_at,
attempt_count/max_attempts, timestamps. Indexes on (status,priority,created_at), job_type, source_id,
lease.

`assistant_enrichment_receipts`: receipt_id (PK), job_id, job_type, worker_id, runtime, model_name,
prompt_version, input_digest, output_digest, source_digest_at_completion, card_digest_at_completion,
result_json, applied_status (enum CHECK), safety_flags_json, error_message, created_at. Index
(job_id, created_at).

Enum values — status: queued/claimed/running/completed/failed/stale/skipped/cancelled;
job_type: source_summary/claim_extraction/backlink_suggestions/claim_validation(reserved);
applied_status: stored_only/candidate_claims_ingested/rejected/stale_rejected/failed.

Migration proof (fresh DB, apply twice): `apply -> 101, 101`; tables
`['assistant_enrichment_jobs','assistant_enrichment_receipts']`; CHECK rejects bad job_type /
missing provenance / bad applied_status. `LATEST_SCHEMA_VERSION == 101`.
