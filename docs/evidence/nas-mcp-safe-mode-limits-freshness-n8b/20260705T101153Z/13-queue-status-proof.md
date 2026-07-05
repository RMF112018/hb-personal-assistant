# 13 — Queue Status Proof

`hb_queue_status` returns source-intelligence indexer queue counts by disposition + last-event
timestamp — no payloads.

`test_queue_status_returns_counts` (seeded `source_intelligence_events` with one `queued`, one
`error`):
```json
{ "status": "ok", "queued_count": 1, "error_count": 1, "processing_count": 0,
  "done_count": 0, "skipped_count": 0, "last_event_at": "2026-07-05 09:05:00" }
```
When the events table is absent → `{status: not_configured}` (explicit). Read-only; available in
safe mode; requires origin auth. No `rel_path`, source content, or decrypted body is returned —
counts + one timestamp only.
