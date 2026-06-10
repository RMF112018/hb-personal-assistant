# 01 — Schema and Policy Strategy (V49)

```text
schema_head_before: 48
schema_head_after:  49   (additive; V1-V48 untouched; idempotent re-apply verified)
migration name:     v49_email_calendar_full_raw_content_and_projections
```

## Additive ADD COLUMN on the three V42 raw tables (guarded by PRAGMA table_info)

| table | added columns |
|---|---|
| `email_message_raw_content` | source_quality (DEFAULT `metadata_only`), raw_capture_run_id, source_record_ref, source_record_id, source_updated_at_utc, payload_hash, raw_content_schema_version (DEFAULT `email_raw_v1`), raw_sidecar_json |
| `email_thread_raw_context` | source_quality, raw_capture_run_id, payload_hash, raw_content_schema_version (DEFAULT `email_thread_raw_v1`) |
| `calendar_event_raw_content` | source_quality, raw_capture_run_id, source_record_ref, source_record_id, source_updated_at_utc, payload_hash, raw_content_schema_version (DEFAULT `calendar_raw_v1`), join_url_policy (DEFAULT `local_db_only`), raw_sidecar_json |

## New structured projection tables (registry-derived; mirror the Procore V47 pattern)

```text
email_raw_message_structured                + email_raw_message_recipients_structured
                                            + email_raw_message_attachments_structured
email_raw_thread_structured                 + email_raw_thread_messages_structured
calendar_raw_event_structured               + calendar_raw_event_attendees_structured
                                            + calendar_raw_event_recurrence_structured
                                            + calendar_raw_event_locations_structured
```

Every structured table carries: `raw_row_id` link to its raw row, `source_quality`,
`projection_schema_version` (`email_calendar_projection_v1`), `payload_hash`, `idempotency_key`,
`payload_sidecar_json` (lossless), and the zero-CHECK guards
`raw_body_emitted_to_evidence = 0`, `external_writeback_performed = 0`.

## New receipt / diagnostic tables

```text
email_calendar_raw_ingestion_runs   (CHECK raw_body_emitted = 0, external_writeback_performed = 0)
raw_content_source_quality_snapshots
email_calendar_projection_runs      (CHECK raw_body_emitted = 0, external_writeback_performed = 0)
email_calendar_projection_coverage  (the completeness proof: counts only)
```

## Source-quality precedence

Ladder: `graph_full_body` / `graph_full_event_body` (100) > `graph_body_preview_only` (70) >
`redacted_legacy_projection` (20) > `metadata_only` (0). Enforced at TWO layers:
1. **Raw upsert** (`ON CONFLICT … CASE WHEN incoming_rank >= existing_rank`): a lower-quality
   re-capture updates only provenance metadata and never wipes local-private body content.
2. **Projection engine**: a lower-quality raw row is `skipped_higher_quality` and never
   downgrades an existing structured row.

## Unconditional reconcile (mirrors V48)

`reconcile_structured_columns()` runs every apply and additively `ALTER TABLE ADD COLUMN`s any
registry-required curated column missing from a structured table (self-heals registry drift).
A parity test asserts every registry-required column physically exists.

## Tests

`tests/test_email_calendar_full_raw_content_ingestion.py` — idempotent V49 apply, head==49,
added columns present, structured+receipt tables present, legacy/V48 tables preserved,
DDL↔registry parity, guard CHECK rejects `raw_body_emitted=1`.
