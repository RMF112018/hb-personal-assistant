# Phase 04A Prompt 04 — RFI Live Sync (parents + replies)

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** `live_apply` (writes to local `procore_live_records` only; no source-system mutation)
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`, `--apply --sqlite-only`
**Caps:** `--max-pages 1 --max-items 5` (parent); child fetch caps internally at `max_pages=1, max_items=50` per parent.

This file records the first **capped live SQLite apply** in Phase 04A. The
orchestrator extends the rfis path with an N+1 child fetch to
`/rest/v1.0/projects/{project_id}/rfis/{rfi_id}/replies`, persisting parent
RFIs as `endpoint_id="rfis"` and replies as `endpoint_id="rfi-responses"`
with `parent_procore_id` populated.

## Pre-state

| Endpoint | `records count` |
| --- | --- |
| `rfis` | 0 |
| `rfi-responses` | 0 |

## Apply command

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint rfis \
  --apply --sqlite-only \
  --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

## Apply receipt (redacted)

- `receipt_id`: `2e182fb3-f3af-4a67-88df-3b20e18872e0`
- `sync_run_id`: `2e182fb3-f3af-4a67-88df-3b20e18872e0`
- `mode`: `live_apply`
- `state`: `success` · `status`: `success`
- `http_method`: `GET`
- `request_count`: 1
- `retrieved_count`: 5 (parent RFIs from one page)
- `parent_retrieved_count`: 5 · `parent_normalized_count`: 5 · `parent_upserted_count`: 5
- `child_endpoint_id`: `rfi-responses`
- `child_retrieved_count`: 6 · `child_normalized_count`: 6 · `child_upserted_count`: 6
- `child_errors_count`: 0
- `normalized_count`: 11 (parents + children)
- `sqlite_upserted_count`: 11 (parents + children)
- `sqlite_total_count_after`: 5 (rfis only; child total tracked separately)
- `raw_body_persisted`: false · `secrets_redacted`: true
- `reason_codes`: `[]` · `redacted_errors`: `[]`
- `started_at`: `2026-05-28T17:07:06.517056+00:00`
- `completed_at`: `2026-05-28T17:07:09.438754+00:00`

## Post-state (after first apply)

| Endpoint | `records count` |
| --- | --- |
| `rfis` | 5 |
| `rfi-responses` | 6 |

## Idempotency re-run

Same command, same caps, same project. Apply ran again successfully:

- `receipt_id`: `4b092288-ce3a-48de-8318-f5256e758882`
- `parent_upserted_count`: 5 · `child_upserted_count`: 6 · `sqlite_upserted_count`: 11
- `state`: `success`

Post counts after the second apply:

| Endpoint | `records count` |
| --- | --- |
| `rfis` | 5 (no duplicates) |
| `rfi-responses` | 6 (no duplicates) |

The upsert-by-(project_key, endpoint_id, parent_procore_id, procore_record_id) primary key guarantees zero duplication. `sqlite_upserted_count=11` on the re-run reflects the number of upsert *operations* (UPDATE rows still count), not new inserts.

## Sample row attestation (read-only `sqlite3` inspection)

Parent RFI row (truncated `canonical_json_redacted`):

```json
{"created_at": "2026-05-19T18:32:06Z", "due_date": "2026-05-22",
 "initiated_at": "2026-05-19T18:32:06Z", "number": "C-351",
 "status": "closed", "subject": "RFI 351 Outlet for Range in Unit Kitchens",
 "updated_at": "2026-05-27T13:55:46Z"}
```

Reply row (canonical_json_redacted): `{"id": 40076235}`

- Reply rows persist only canonical metadata; the `body` text from
  `normalize_rfi_reply` is never written — only the SHA-256 hash-prefix
  summary inside the normalized record (and even that hash summary is
  recorded only when present, never the raw text).
- `review_required = 1` on every `rfi-responses` row (enforced by
  `normalize_rfi_reply` per the prompt-04 stop condition).
- `raw_body_persisted = 0` on every row in `procore_live_records` and on
  every `procore_live_sync_runs` row (V6 schema CHECK constraint).

## No-secret / no-raw-body attestation

Direct SQLite scan after the apply:

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE canonical_json_redacted LIKE '%Bearer%'
    OR canonical_json_redacted LIKE '%client_secret%'
    OR canonical_json_redacted LIKE '%refresh_token%'
    OR canonical_json_redacted LIKE '%access_token%';
```

Result: `0`. No OAuth access token, refresh token, client secret, or
`Authorization` header value appears in any persisted cell.

All 12+ HTTP calls observed during the apply went through
`ProcoreHTTPClient._require_get` (GET-only enforcement). No 4xx/5xx other
than the absence of failures (`child_errors_count=0`).

## Promotion outcomes

- `rfis`: remains `live_verified=True`; smoke from Prompt 03 plus this
  live apply both successful.
- `rfi-responses`: remains `live_verified=False` (no direct CLI invocation
  path — child rows are populated only as a byproduct of the rfis parent
  fetch). `verification_reason` updated to
  `populated_via_rfis_parent_fetch_2026-05-28` to truthfully describe the
  data lineage.

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync --project tropical \
  --endpoint rfis --apply --sqlite-only \
  --max-pages 1 --max-items 5 --confirm-live-get --json

hb-assistant procore live records count --project tropical --endpoint rfis --json
hb-assistant procore live records count --project tropical --endpoint rfi-responses --json
```

Acceptance: receipt `state=success`, `parent_upserted_count>=1`, `child_upserted_count>=0`, `raw_body_persisted=false`. Re-running does not increase row counts.
