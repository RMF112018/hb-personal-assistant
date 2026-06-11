# 03 — Calendar Full Raw Ingestion (Pass 1, summarized)

Hardening landed in Pass 1 (commit `3e50fd7e`).

- `calendar_event_raw_content` now persists `source_quality` (`graph_full_event_body` ladder),
  `payload_hash`, `raw_capture_run_id`, `source_updated_at_utc`, `raw_content_schema_version`,
  `join_url_policy` (DEFAULT `local_db_only`), and a lossless `raw_sidecar_json`.
- `ReadOnlyCalendarClient.get_event()` `$select` widened (bodyPreview, locations, isAllDay, showAs,
  categories, type, seriesMasterId, created/lastModified, originalStart, onlineMeetingProvider).
  The extra fields are preserved losslessly in `raw_sidecar_json`; the online-meeting **join URL is
  scrubbed out of the sidecar** and kept only in the `join_url` column under `join_url_policy`.
- `upsert_calendar_event_raw_content` classifies `source_quality`, computes `payload_hash`, and
  enforces the same data-layer downgrade prevention; the indexer records a `raw_content_access_events`
  row on the raw-persist path.

Counts/source-quality/null-rate only; no raw agenda bodies or join URLs in evidence. Fixture tests:
`tests/test_email_calendar_full_raw_content_ingestion.py`.
