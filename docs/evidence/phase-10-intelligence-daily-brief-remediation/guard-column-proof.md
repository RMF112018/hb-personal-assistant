# Guard-Column Proof

After the full live workflow (dry-run + 2× apply + intelligence runs) on the `/tmp` Dev DB copy, every
guard column across all tables summed to **0** — no raw content persisted and no external action taken.

Columns scanned (per table, summed over all rows): `raw_email_body_persisted`,
`raw_document_text_persisted`, `raw_calendar_payload_persisted`, `raw_procore_payload_persisted`,
`raw_prompt_persisted`, `raw_response_persisted`, `signed_url_persisted`, `download_url_persisted`,
`external_writeback_performed`, `graph_writeback_performed`, `procore_writeback_performed`,
`email_send_performed`, `calendar_mutation_performed` (present on `daily_brief_action_candidates` and
`local_model_run_receipts`).

| Metric | Value |
| --- | --- |
| Guard-column grand total (all tables, all rows) | **0** |
| `local_model_run_receipts` after apply | 2 (hash-only; one written by apply `--with-intelligence`) |
| Receipt raw/writeback guard columns | 0 |

The apply path writes only a hash-only receipt (SHA-256[:12] of input context and output, plus
metadata: status, schema_valid, latency, fallback_used). No raw prompt or model response is stored.
