# Phase 04A Prompt 06 — Observation Live Sync

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** `live_apply` (writes to local `procore_live_records` only; no source-system mutation)
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`, `--apply --sqlite-only`
**Caps:** first apply `--max-pages 1 --max-items 5`; E2E target apply `--max-pages 3 --max-items 100` (integrated E2E acceptance overlay caps); idempotency re-run at the same E2E caps.

This file records the **observation** parent-only capped live SQLite apply
for the Phase 04A `observations` endpoint
(`/rest/v1.0/projects/{project_id}/observations/items`). Observations is a
single top-level surface with `sensitivity="high"`; review routing is
driven by the four-field heuristic in `normalize_observation`
(`_safety_route_decision()` over status / type / subtype / title /
description) plus the supplementary `procore-observation-safety` rule in
`procore_sensitive_routing_rules.yaml`.

## Outcome summary

| Endpoint        | Smoke   | Apply       | Promotion          |
| ---             | ---     | ---         | ---                |
| `observations`  | success | success     | promoted to `live_verified=True` |

Per the integrated E2E acceptance overlay, the touched endpoint proved live
GET + normalization + SQLite upsert + `records count` end-to-end.

## Pre-state

| Endpoint       | `records count` |
| ---            | ---             |
| `observations` | 0               |

## Live smoke — `observations`

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint observations \
  --confirm-live-get --json
```

- `receipt_id`: `2d0a091f-bb8c-465f-a7c1-54c948e2f08d`
- `mode`: `live_smoke`
- `state`: `success` · `status`: `success`
- `retrieved_count`: 10 · `normalized_count`: 10
- `sqlite_upserted_count`: 0 (smoke never writes)
- `reason_codes`: `[]` · `redacted_errors`: `[]`
- `started_at`: `2026-05-28T19:50:15.056553+00:00`
- `completed_at`: `2026-05-28T19:50:15.873836+00:00`

## Live apply — `observations` (caps 1/5)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint observations \
  --apply --sqlite-only \
  --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

- `receipt_id`: `40570cb5-07d2-4e90-8627-05f08587a45a`
- `sync_run_id`: `40570cb5-07d2-4e90-8627-05f08587a45a`
- `mode`: `live_apply`
- `state`: `success` · `status`: `success`
- `http_method`: `GET`
- `retrieved_count`: 5 · `normalized_count`: 5 · `sqlite_upserted_count`: 5
- `sqlite_total_count_after`: 5
- `raw_body_persisted`: false · `secrets_redacted`: true
- `reason_codes`: `[]` · `redacted_errors`: `[]`
- `started_at`: `2026-05-28T19:50:30.363563+00:00`
- `completed_at`: `2026-05-28T19:50:30.957616+00:00`

## Live apply — `observations` (caps 3/100, E2E target)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint observations \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

- `receipt_id`: `b6a44a01-b254-4af7-8394-a7fac16d6811`
- `state`: `success` · `status`: `success`
- `retrieved_count`: 100 · `normalized_count`: 100 · `sqlite_upserted_count`: 100
- `sqlite_total_count_after`: 100
- `started_at`: `2026-05-28T19:50:31.435097+00:00`
- `completed_at`: `2026-05-28T19:50:32.597863+00:00`

## Idempotency re-run — `observations` (caps 3/100, re-run)

Same command, same caps, same project.

- `receipt_id`: `a2c28ee9-e4a4-42a8-bf2a-3921b2ff6a57`
- `state`: `success` · `status`: `success`
- `retrieved_count`: 100 · `sqlite_upserted_count`: 100
- `sqlite_total_count_after`: 100 (unchanged from prior run)
- `started_at`: `2026-05-28T19:50:33.078470+00:00`
- `completed_at`: `2026-05-28T19:50:34.131286+00:00`

Post counts after the idempotency re-run:

| Endpoint       | `records count` |
| ---            | ---             |
| `observations` | 100 (no duplicates) |

The upsert-by-(project_key, endpoint_id, parent_procore_id,
procore_record_id) primary key guarantees zero duplication.
`sqlite_upserted_count=100` on the re-run reflects the number of upsert
*operations* (UPDATE rows still count), not new inserts.

## Review-routing distribution (live data)

After the apply, every persisted observation row carries
`review_required=1`. Every row's `sensitive_reason` is `assignee_missing`,
which is the conservative fallback path in `_safety_route_decision()`:

```sql
SELECT review_required, COUNT(*) FROM procore_live_records
 WHERE endpoint_id='observations' GROUP BY review_required;
```
Result: `1 | 100`.

```sql
SELECT sensitive_reason, COUNT(*) FROM procore_live_records
 WHERE endpoint_id='observations' GROUP BY sensitive_reason;
```
Result: `assignee_missing | 100`.

This outcome reflects real Procore submission patterns: in the `tropical`
data set, the 100 observations sampled all closed without an `assignee_id`
populated. The normalizer therefore routes every row for review per the
prompt's "high-sensitivity review routing" requirement — there is no live
example of the `default_low_risk` path. The unit test
`test_observations_apply_persists_with_heuristic_review_routing` exercises
all three heuristic paths (safety fragment hit, default low-risk with
assignee present, assignee-missing fallback) on synthetic fixtures, so the
heuristic contract remains fully covered.

## Sample row attestation (read-only `sqlite3` inspection)

Observation row 17028764 (truncated `canonical_json_redacted`):

```json
{"closed_at": "2025-01-10T14:49:20Z",
 "created_at": "2025-01-06T18:02:16Z",
 "due_date": "2025-01-16", "number": "1",
 "priority": "High", "status": "closed",
 "type": {"active": true, "category": "Safety", "category_key": ...
```

- Row carries canonical observation metadata only; the description body
  is reduced to a SHA-256 hash-only `description_summary` in the
  normalized record (never written verbatim).
- `raw_body_persisted = 0` on every observation row (V6 CHECK constraint
  enforced).
- `review_required = 1` and `sensitive_reason = "assignee_missing"` on
  every row in this live data set.

## No-secret / no-raw-body attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='observations'
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%client_secret%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%access_token%');
```
Result: `0`. No OAuth access token, refresh token, client secret, or
`Authorization` header value appears in any persisted cell.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id='observations' AND raw_body_persisted != 0;
```
Result: `0`. Every row honors the schema-level `raw_body_persisted = 0`
CHECK constraint.

All HTTP calls observed during the smoke + applies went through
`ProcoreHTTPClient._require_get` (GET-only enforcement). No method other
than `GET` was recorded on the transport.

## Sync-run rows (audit trail)

```sql
SELECT sync_run_id, endpoint_id, mode, status, state,
       retrieved_count, sqlite_upserted_count
  FROM procore_live_sync_runs
 WHERE started_at_utc > '2026-05-28' AND endpoint_id='observations'
 ORDER BY started_at_utc;
```

```
40570cb5-... | observations | live_apply | success | success |   5 |   5
b6a44a01-... | observations | live_apply | success | success | 100 | 100
a2c28ee9-... | observations | live_apply | success | success | 100 | 100
```

The smoke run (`live_smoke`, receipt `2d0a091f`) intentionally does not
write to `procore_live_sync_runs`; its receipt is captured ephemerally
and recorded above only.

## Promotion outcome

- `observations`: promoted from `live_verified=False` to
  `live_verified=True`. `verification_reason` updated from
  `observation_endpoint_pending_live_smoke` to
  `live_smoke_passed_2026-05-28:2d0a091f`.

The verified-set test
(`test_procore_endpoint_registry::test_verified_endpoints_match_phase04a_matrix`)
now expects five endpoints: `projects`, `rfis`, `submittals`,
`daily-log-weather`, `observations`. The unverified-set parameterized
test (`tests/test_procore_live_sync_unverified_fail_closed.py::_UNVERIFIED_IDS`)
goes from 9 → 8 entries.

## Verification (repeatable, post-commit)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync --project tropical \
  --endpoint observations --apply --sqlite-only \
  --max-pages 3 --max-items 100 --confirm-live-get --json

hb-assistant procore live records count --project tropical --endpoint observations --json
```

Acceptance:
- Receipt `state=success`, `sqlite_upserted_count>=1`,
  `raw_body_persisted=false`.
- Re-running at the same caps does not increase row counts.
- Every persisted observation row has `review_required=1` for live
  `tropical` data while the `assignee_missing` fallback dominates;
  synthetic fixtures continue to exercise the full heuristic
  decision tree (safety / default_low_risk / assignee_missing).
