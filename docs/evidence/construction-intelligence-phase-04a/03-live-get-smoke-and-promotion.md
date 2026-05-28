# Phase 04A Prompt 03 — Live GET Smoke and Endpoint Promotion

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** `live_smoke` (no SQLite writes; GET-only)
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`

This file records the first live Procore API calls in Phase 04A. The
orchestrator under test is `hb_assistant.procore.live_sync.run_live_sync`
invoked via the `hb-assistant procore live smoke` CLI surface (landed in
prior commit `1b6f9a2`).

## Pre-flight

| Check | Source | Outcome |
| --- | --- | --- |
| Live env gate | `HB_PROCORE_LIVE=1` set in shell | ✓ |
| Operator confirm flag | `--confirm-live-get` | ✓ |
| OAuth readiness | `hb-assistant procore auth status --json` reported `ready_for_live_calls=true`, refresh token present, access token expired but auto-refreshable | ✓ |
| Pilot mapping | `procore mapping validate` shows `tropical -> 2525840`, status `pilot`, `mapped=true` | ✓ |
| Endpoint registry | `procore live endpoints list` returns 14 canonical rows | ✓ |

## Smoke command template

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical \
  --endpoint <endpoint-id> \
  --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

## Per-endpoint smoke receipts (redacted)

### `projects`

- `receipt_id`: `7703b766-2b8a-49b5-8c72-1687a1b48204`
- `state`: `success` · `status`: `success`
- `http_method`: `GET` · `request_count`: 1 · `retrieved_count`: 5 · `normalized_count`: 5
- `sqlite_upserted_count`: 0 · `raw_body_persisted`: false · `secrets_redacted`: true
- `reason_codes`: `[]` · `redacted_errors`: `[]`

### `rfis`

- `receipt_id`: `09113b6d-e901-4c33-a32d-0fe997078f18`
- `state`: `success` · `status`: `success`
- `http_method`: `GET` · `request_count`: 1 · `retrieved_count`: 5 · `normalized_count`: 5
- `sqlite_upserted_count`: 0 · `raw_body_persisted`: false · `secrets_redacted`: true
- `reason_codes`: `[]` · `redacted_errors`: `[]`

### `submittals`

- `receipt_id`: `d9506311-8d98-4656-82ed-f842638f1850`
- `state`: `success` · `status`: `success`
- `http_method`: `GET` · `request_count`: 1 · `retrieved_count`: 5 · `normalized_count`: 5
- `sqlite_upserted_count`: 0 · `raw_body_persisted`: false · `secrets_redacted`: true
- `reason_codes`: `[]` · `redacted_errors`: `[]`

### `meetings` — **FAIL**

- `receipt_id`: `8846c746-6fcd-4cd0-a7f5-1311ce3c5c7c`
- `state`: `transport_error` · `status`: `error`
- `http_method`: `GET` · `request_count`: 0 · `retrieved_count`: 0 · `normalized_count`: 0
- `sqlite_upserted_count`: 0 · `raw_body_persisted`: false · `secrets_redacted`: true
- `reason_codes`: `["transport_error:http_error"]`
- `redacted_errors`: `[{"code": "http_error", "status": 404}]`
- **Root cause:** the adapter path template
  `/rest/v1.0/projects/{project_id}/meetings` returned HTTP 404 from
  Procore. The Procore REST surface for meetings differs (likely
  `/rest/v1.1/...` or a different scoping convention). This is a docs/contract
  defect, not a transport or credential fault.

### `daily-log-weather`

- `receipt_id`: `e4d9f384-25d6-4eca-851d-c62ea36c09b5`
- `state`: `success` · `status`: `success`
- `http_method`: `GET` · `request_count`: 1 · `retrieved_count`: 1 · `normalized_count`: 1
- `sqlite_upserted_count`: 0 · `raw_body_persisted`: false · `secrets_redacted`: true
- `reason_codes`: `[]` · `redacted_errors`: `[]`

## SQLite no-write verification

After every smoke, `hb-assistant procore live records count --project tropical --endpoint <id> --json` returned `count: 0`:

| Endpoint | `records count` |
| --- | --- |
| `projects` | 0 |
| `rfis` | 0 |
| `submittals` | 0 |
| `meetings` | 0 |
| `daily-log-weather` | 0 |

Smoke mode honors its contract: no row is written to `procore_live_records`.

## Promotion table

| Endpoint | Pre-smoke `live_verified` | Smoke result | Post-smoke `live_verified` | New `verification_reason` |
| --- | --- | --- | --- | --- |
| `projects` | true | success | true (kept) | `live_smoke_passed_2026-05-28:7703b766` |
| `rfis` | true | success | true (kept) | `live_smoke_passed_2026-05-28:09113b6d` |
| `submittals` | true | success | true (kept) | `live_smoke_passed_2026-05-28:d9506311` |
| `meetings` | true | 404 transport error | **false (demoted)** | `live_smoke_failed_2026-05-28:http_404_at_/rest/v1.0/projects/{project_id}/meetings` |
| `daily-log-weather` | true | success | true (kept) | `live_smoke_passed_2026-05-28:e4d9f384` |

Unverified endpoints (`rfi-responses`, `submittal-responses`, `submittal-packages`, `observations`, `meeting-topics`, `daily-log-manpower`, `daily-log-notes`, `daily-log-deliveries`, `daily-log-delays-review-routed`) were not smoked in this prompt and remain `live_verified=false`. Their promotion is reserved for a follow-up prompt that includes a docs check for the correct Procore path template.

## No-secret / no-raw-body attestation

- No Procore response body is persisted: every smoke receipt above carries `raw_body_persisted=false`, and `procore_live_records` row counts are 0.
- No OAuth access token, refresh token, or client secret appears in any receipt, evidence row, log message, or SQLite cell. The CLI surface routes every response through `hb_assistant.procore.redaction.redact_response` / `redact_request` / `redact_body` before any consumer sees it; the HTTP client obtains the bearer access token at request time and never keeps it on the instance.
- All five observed HTTP methods on the wire were `GET`. The `ProcoreHTTPClient._require_get` guard rejects any non-GET attempt before the transport is called.

## Follow-up actions

1. Investigate the correct Procore REST path/version for the meetings list endpoint and update `endpoints.py` (`path_template`) when verified; re-smoke and promote.
2. Smoke the 9 currently-unverified candidate endpoints in a future Phase 04A prompt with a discovery flag and update the registry accordingly.

## Verification commands (post-commit, repeatable)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke --project tropical --endpoint rfis \
  --max-pages 1 --max-items 5 --confirm-live-get --json
hb-assistant procore live records count --project tropical --endpoint rfis --json
hb-assistant procore live endpoints list --json
```
