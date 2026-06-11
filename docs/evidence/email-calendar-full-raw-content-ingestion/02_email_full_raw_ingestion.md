# 02 — Email Full Raw Ingestion (Pass 1, summarized)

Hardening landed in Pass 1 (commit `3e50fd7e`); see `01_schema_and_policy_strategy.md`.

- `email_message_raw_content` now persists `source_quality`, `payload_hash`, `raw_capture_run_id`,
  `source_updated_at_utc`, `raw_content_schema_version`, and a lossless `raw_sidecar_json` in
  addition to subject/preview/body_text/body_html/sender/recipients/timestamps/attachment metadata.
- `upsert_email_message_raw_content` classifies `source_quality` from body presence
  (`graph_full_body` > `graph_body_preview_only` > `metadata_only`) and computes `payload_hash`.
- **Data-layer downgrade prevention:** the upsert `ON CONFLICT … CASE WHEN incoming_rank >=
  existing_rank` keeps local-private body content; a lower-quality re-capture updates only
  provenance metadata (proven by `test_lower_quality_cannot_overwrite_full_body`).
- The indexer records a `raw_content_access_events` row on the raw-persist path and stamps
  `raw_capture_run_id` + `source_updated_at_utc`; attachment **content** is never stored (metadata only).

Counts/source-quality only; no raw bodies in evidence. Fixture tests:
`tests/test_email_calendar_full_raw_content_ingestion.py`.
