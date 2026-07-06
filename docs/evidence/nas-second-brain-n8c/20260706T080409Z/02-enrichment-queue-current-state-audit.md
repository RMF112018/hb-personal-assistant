# Enrichment Queue — Pre-N8C-5 State Audit

Before N8C-5 there was no enrichment/job-queue layer. The closest precedents (reused as models):
- `source_index_repository` durable event queue (`enqueue_event`/`claim_queued`/`requeue_stuck`) —
  the atomic conditional-UPDATE claim pattern.
- `source_intelligence_summaries` (V94) receipts (`source_sha256`+`prompt_version`) — the
  snapshot-at-enqueue / recheck-at-completion digest pattern.
- `construction/classification/client.OllamaChatClient` + `source_local_summary` (qwen2.5:14b) —
  the local-model generation path (wrapped, not reimplemented).
- Existing backend auto-worker `_quality_poll_loop` in the FastAPI lifespan — the anti-pattern the
  enrichment worker deliberately avoids (no lifespan hook).
