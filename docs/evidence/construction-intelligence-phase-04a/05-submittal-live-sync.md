# Phase 04A Prompt 05 — Submittal Live Sync (parents + responses N+1 + packages sibling)

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** `live_apply` (writes to local `procore_live_records` only; no source-system mutation)
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`, `--apply --sqlite-only`
**Caps:** first apply `--max-pages 1 --max-items 5`; idempotency apply `--max-pages 3 --max-items 100` (the integrated E2E acceptance overlay target); child fetch caps internally at `max_pages=1, max_items=50` per parent.

This file records the **submittal family** capped live SQLite apply.
The orchestrator extends the submittals path with an N+1 child fetch to
`/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses`,
intended to persist parent submittals as `endpoint_id="submittals"` and
responses as `endpoint_id="submittal-responses"` with `parent_procore_id`
populated. The sibling `submittal-packages` endpoint
(`/rest/v1.0/projects/{project_id}/submittals/packages`) is an independent
top-level invocation, not a child of a specific submittal.

## Outcome summary

| Endpoint                | Smoke   | Apply       | Promotion      |
| ---                     | ---     | ---         | ---            |
| `submittals`            | success | success     | remains verified |
| `submittal-responses`   | n/a (no standalone path) | structured fail-closed via parent N+1 — HTTP 404 | remains unverified |
| `submittal-packages`    | structured fail-closed — HTTP 404 | not attempted | remains unverified, demoted with failure reason |

Per the integrated E2E acceptance overlay, every endpoint touched either
(1) proved live GET + normalization + SQLite upsert + `records count`, or
(2) failed closed with a structured receipt explaining the blocker.

## Pre-state

| Endpoint               | `records count` |
| ---                    | ---             |
| `submittals`           | 0               |
| `submittal-responses`  | 0               |
| `submittal-packages`   | 0               |

## Live smoke — `submittals` (success)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint submittals \
  --confirm-live-get --json
```

- `receipt_id`: `a08c3739-957d-432d-b95a-8ee663ccda44`
- `mode`: `live_smoke`
- `state`: `success` · `status`: `success`
- `retrieved_count`: 10 · `normalized_count`: 10
- `sqlite_upserted_count`: 0 (smoke never writes)
- `reason_codes`: `[]` · `redacted_errors`: `[]`
- `started_at`: `2026-05-28T19:30:54.932530+00:00`
- `completed_at`: `2026-05-28T19:30:56.062343+00:00`

## Live smoke — `submittal-packages` (HTTP 404, fail-closed)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint submittal-packages \
  --confirm-live-get --json
```

- `receipt_id`: `126c2e9b-afc5-4461-ac67-d9f4eb008891`
- `mode`: `live_smoke`
- `state`: `transport_error` · `status`: `error`
- `retrieved_count`: 0 · `sqlite_upserted_count`: 0
- `reason_codes`: `['transport_error:http_error']`
- `redacted_errors`: `[{"code": "http_error", "status": 404}]`
- `started_at`: `2026-05-28T19:32:43.349802+00:00`
- `completed_at`: `2026-05-28T19:32:43.872762+00:00`

The path template `/rest/v1.0/projects/{project_id}/submittals/packages`
returned HTTP 404. The endpoint was demoted in the registry with reason
`live_smoke_failed_2026-05-28:http_404_at_/rest/v1.0/projects/{project_id}/submittals/packages`.
Root-cause path discovery (e.g. `/submittal_packages`, `/v1.1/...`,
company-scoped paths) is **deferred to a follow-up prompt**, mirroring the
prior-session disposition of `meetings`. No path probing was performed
under Prompt 05 to honor the no-improvisation stop condition.

## Live apply — `submittals` (caps 1/5)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint submittals \
  --apply --sqlite-only \
  --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

- `receipt_id`: `082fc171-316c-4fab-bd01-8b9bbc4d3377`
- `sync_run_id`: `082fc171-316c-4fab-bd01-8b9bbc4d3377`
- `mode`: `live_apply`
- `state`: `partial_success` · `status`: `partial`
- `http_method`: `GET`
- `retrieved_count`: 5 (parent submittals from one page)
- `parent_retrieved_count`: 5 · `parent_normalized_count`: 5 · `parent_upserted_count`: 5
- `child_endpoint_id`: `submittal-responses`
- `child_retrieved_count`: 0 · `child_normalized_count`: 0 · `child_upserted_count`: 0
- `child_errors_count`: 5 (every per-submittal `/responses` fetch returned HTTP 404)
- `normalized_count`: 5 · `sqlite_upserted_count`: 5 (parents only)
- `sqlite_total_count_after`: 5
- `raw_body_persisted`: false · `secrets_redacted`: true
- `redacted_errors`: 5 entries, each
  `{"child_transport_error": "http_error", "status": 404, "parent_procore_id": "<id>"}`
- `started_at`: `2026-05-28T19:33:19.095632+00:00`
- `completed_at`: `2026-05-28T19:33:21.012325+00:00`

The orchestrator persisted every parent submittal and surfaced each child
404 in `redacted_errors` without aborting the run — the fail-closed contract
for child fetches is verified end-to-end in production.

## Live apply — `submittals` (caps 3/100, E2E target)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint submittals \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

- `receipt_id`: `414dc0a1-0e47-446f-8a36-37ba2161722a`
- `state`: `partial_success` (child 404 contract drift; parents all succeed)
- `parent_upserted_count`: 100 · `child_upserted_count`: 0 · `child_errors_count`: 100
- `sqlite_total_count_after`: 100
- `started_at`: `2026-05-28T19:34:21.144212+00:00`
- `completed_at`: `2026-05-28T19:35:10.467774+00:00`

## Idempotency re-run — `submittals` (caps 3/100, re-run)

Same command, same caps, same project. Apply ran again successfully:

- `receipt_id`: `f2d53e9d-5670-4548-a00a-00b82a522405`
- `parent_upserted_count`: 100 · `child_upserted_count`: 0 · `sqlite_upserted_count`: 100
- `sqlite_total_count_after`: 100 (unchanged from prior run)
- `state`: `partial_success`
- `started_at`: `2026-05-28T19:35:23.739610+00:00`
- `completed_at`: `2026-05-28T19:36:09.499315+00:00`

Post counts after the idempotency re-run:

| Endpoint               | `records count` |
| ---                    | ---             |
| `submittals`           | 100 (no duplicates) |
| `submittal-responses`  | 0 (child path 404)  |
| `submittal-packages`   | 0 (sibling path 404) |

The upsert-by-(project_key, endpoint_id, parent_procore_id, procore_record_id)
primary key guarantees zero duplication. `sqlite_upserted_count=100` on the
re-run reflects the number of upsert *operations* (UPDATE rows still count),
not new inserts.

## Sample row attestation (read-only `sqlite3` inspection)

Parent submittal row (truncated `canonical_json_redacted`):

```json
{"created_at": "2024-10-11T14:53:00Z", "due_date": "2024-10-25",
 "number": "1",
 "specification_section": {"current_revision_id": 43396777,
   "description": "Water Utilities", "id": 35488456,
   "label": "3...
```

- Row carries canonical submittal metadata only; no raw description, no
  raw response/comment bodies (the `submittal-responses` child fetch
  never returned data, so no response rows were upserted at all).
- `raw_body_persisted = 0` on every row in `procore_live_records` and on
  every `procore_live_sync_runs` row (V6 schema CHECK constraint).

## No-secret / no-raw-body attestation

Direct SQLite scan after the apply:

```sql
SELECT endpoint_id, COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'submittal%'
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%client_secret%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%access_token%')
 GROUP BY endpoint_id;
```

Result: `0` rows. No OAuth access token, refresh token, client secret, or
`Authorization` header value appears in any persisted cell for any
submittal-family endpoint.

```sql
SELECT endpoint_id, COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'submittal%' AND raw_body_persisted != 0
 GROUP BY endpoint_id;
```

Result: `0` rows. Every row honors the schema-level
`raw_body_persisted = 0` CHECK constraint.

All HTTP calls observed during the smokes + applies went through
`ProcoreHTTPClient._require_get` (GET-only enforcement). No method other
than `GET` was recorded on the transport.

## Sync-run rows (audit trail)

```sql
SELECT sync_run_id, endpoint_id, mode, status, state,
       retrieved_count, sqlite_upserted_count
  FROM procore_live_sync_runs
 WHERE started_at_utc > '2026-05-28'
   AND endpoint_id LIKE 'submittal%'
 ORDER BY started_at_utc;
```

```
082fc171-... | submittals | live_apply | partial | partial_success |   5 |   5
414dc0a1-... | submittals | live_apply | partial | partial_success | 100 | 100
f2d53e9d-... | submittals | live_apply | partial | partial_success | 100 | 100
```

Smoke runs (`live_smoke`) intentionally do not write `procore_live_sync_runs`
rows; the smoke `receipt_id`s above are captured ephemerally and recorded
in this evidence file only.

## Promotion outcomes

- `submittals`: remains `live_verified=True`. Pre-existing
  `verification_reason` `live_smoke_passed_2026-05-28:d9506311` from
  Prompt 03 still accurate; this prompt re-confirmed via smoke
  `a08c3739` and three live applies.
- `submittal-responses`: remains `live_verified=False`. `verification_reason`
  updated from `child_endpoint_pending_docs_verification` to
  `live_apply_child_fetch_failed_2026-05-28:http_404_at_/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses`
  to record the live evidence of the contract drift discovered under this
  prompt. By codebase convention, child endpoints (rfi-responses,
  submittal-responses) are not separately promoted; the value of the
  flag is whether the parent apply could populate child rows.
- `submittal-packages`: remains `live_verified=False`. `verification_reason`
  updated from `package_endpoint_pending_docs_verification` to
  `live_smoke_failed_2026-05-28:http_404_at_/rest/v1.0/projects/{project_id}/submittals/packages`.
  Stays out of the verified set until a follow-up prompt verifies the
  correct Procore endpoint path.

The verified-set test (`test_verified_endpoints_match_phase04a_matrix`)
remains at four endpoints: `projects`, `rfis`, `submittals`,
`daily-log-weather`. Prompt 05 contributes no additions.

## Contract-drift backlog

Two Procore endpoint contracts produced HTTP 404 against the live
`tropical` project under bearer-token authenticated GET. Both are
**deferred** to a future prompt that consults current Procore REST docs
and re-smokes against alternate paths (mirroring the disposition of
`meetings` from Prompt 03):

| Endpoint              | Recorded failing path |
| ---                   | ---                   |
| `submittal-responses` | `/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses` |
| `submittal-packages`  | `/rest/v1.0/projects/{project_id}/submittals/packages` |

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync --project tropical \
  --endpoint submittals --apply --sqlite-only \
  --max-pages 3 --max-items 100 --confirm-live-get --json

hb-assistant procore live records count --project tropical --endpoint submittals --json
hb-assistant procore live records count --project tropical --endpoint submittal-responses --json
hb-assistant procore live records count --project tropical --endpoint submittal-packages --json
```

Acceptance:
- `submittals` receipt `state` in `{success, partial_success}`,
  `parent_upserted_count>=1`, `raw_body_persisted=false`.
- Re-running at the same caps does not increase row counts.
- `submittal-responses` and `submittal-packages` counts remain `0` and
  receipts surface structured `transport_error:http_error` / `status=404`
  until the contract-drift backlog above is resolved.
