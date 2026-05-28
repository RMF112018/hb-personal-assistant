# Phase 04A Prompt 08 — Selected Daily Log Live Sync

**Date (UTC):** 2026-05-28
**Pilot project:** `tropical` (Procore project id `2525840`)
**Company:** HB Construction (5280)
**Run mode:** `live_apply` (writes to local `procore_live_records` only; no source-system mutation)
**Operator gates active:** `HB_PROCORE_LIVE=1`, `--confirm-live-get`, `--apply --sqlite-only`
**Caps:** apply at `--max-pages 3 --max-items 100` (integrated E2E acceptance overlay target) with same-caps re-run for idempotency proof.

Prompt 08 extends the daily-log family from a single verified section
(`daily-log-weather` from Prompt 03) to **five** verified sections plus
two **new** canonical adapter rows. The canonical registry grows from
14 to 16 endpoints. Sections carrying free-text content (notes, delays)
land with `review_required=True` and SHA-256 hash-only body summaries;
structured-only sections (manpower, deliveries, inspections) land with
`review_required=False`. The daily construction reports (DCR) endpoint
at `/rest/v1.0/projects/{project_id}/dcrs` returned HTTP 404 against
`tropical` and was demoted with the failure reason recorded.

## Section partition (Prompt 08 policy)

| Section                           | Sensitivity | Promoted | review_required | safety_route | Hash-only fields                     |
| ---                               | ---         | ---      | ---             | ---          | ---                                  |
| `daily-log-weather`               | low         | (Prompt 03) | False          | False        | (none)                               |
| `daily-log-manpower`              | low         | yes      | False           | False        | (none — structured only)             |
| `daily-log-notes`                 | high        | yes      | **True**        | False        | `note`, `body`, `comments`           |
| `daily-log-deliveries`            | medium      | yes      | False           | False        | (none — structured only)             |
| `daily-log-delays-review-routed`  | critical    | yes      | **True**        | **True**     | `description`, `cause`, `safety_violation` |
| `daily-log-inspections` (new)     | medium      | yes      | False           | False        | `comments`, `description`            |
| `daily-log-dcrs` (new)            | medium      | **no** (404) | n/a         | n/a          | n/a                                  |

## Smoke + promotion matrix

| Section                           | Path                                                                | HTTP | Retrieved | Receipt id   | Outcome                       |
| ---                               | ---                                                                 | ---  | ---       | ---          | ---                           |
| `daily-log-manpower`              | `/rest/v1.0/projects/{id}/manpower_logs`                            | 200  | 0         | `d0836094-…` | promoted                       |
| `daily-log-notes`                 | `/rest/v1.0/projects/{id}/notes_logs`                               | 200  | 0         | `49cb933b-…` | promoted (review-routed)       |
| `daily-log-deliveries`            | `/rest/v1.0/projects/{id}/delivery_logs`                            | 200  | 0         | `52f90d5b-…` | promoted                       |
| `daily-log-delays-review-routed`  | `/rest/v1.0/projects/{id}/delay_logs`                               | 200  | 0         | `d3c84564-…` | promoted (review + safety route) |
| `daily-log-inspections`           | `/rest/v1.0/projects/{id}/inspection_logs`                          | 200  | 0         | `e3d4b3c4-…` | promoted (new adapter row)     |
| `daily-log-dcrs`                  | `/rest/v1.0/projects/{id}/dcrs`                                     | 404  | 0         | `ad21cc7a-…` | demoted (contract drift)       |

All five 200-resolving sections returned an empty list against
`tropical` (the project has no live data in those sections at the time
of Prompt 08 execution). The orchestrator therefore validates the full
chain — gate → transport → paginate → normalize → upsert → records
count — with retrieved_count=0 / normalized_count=0 / upserted_count=0
and `state="success"`. Idempotency is trivial.

## Live applies + idempotency proof

Each promoted section ran two `live_apply` runs at the E2E target caps
`--max-pages 3 --max-items 100`. Receipts:

| Section                          | Apply receipt id                              | Re-run receipt id                             | State     | Total after both runs |
| ---                              | ---                                           | ---                                           | ---       | ---                   |
| `daily-log-manpower`             | `0fcc6a31-9cd0-499a-9aa5-5aca127433c3`        | `8653bb05-5b86-42e4-b67a-55b636be86f4`        | success   | 0                     |
| `daily-log-notes`                | `ce11e9fa-bf72-4443-8bf2-3dbdd340dfa1`        | `d4d9b024-36c8-4420-9012-5cd1c2d71d0d`        | success   | 0                     |
| `daily-log-deliveries`           | `2e049653-b3f9-4e33-9c26-ba801fa31ca0`        | `b438fbed-0abf-4f48-b450-8d01020771d8`        | success   | 0                     |
| `daily-log-delays-review-routed` | `9fbf455a-3af9-45ad-b02e-20e77c29a89e`        | `28008b91-a2ec-4c40-b67b-8a328e34ade7`        | success   | 0                     |
| `daily-log-inspections`          | `981f4c0f-1dce-4888-93e5-898cafca5bec`        | `e49c469e-d109-489c-a5d3-ed9f07889169`        | success   | 0                     |

## Post-state `records count` (SQLite-only)

```bash
for s in manpower notes deliveries delays-review-routed inspections dcrs weather; do
  hb-assistant procore live records count --project tropical --endpoint daily-log-$s --json
done
```

Result: all daily-log endpoints return `count: 0`. No live data exists
in `tropical` for the daily-log family at the time of this prompt; the
chain works end-to-end and the upsert is exercised against an empty
result set.

## Sync-run audit trail

```sql
SELECT endpoint_id, mode, status, state, retrieved_count
  FROM procore_live_sync_runs
 WHERE started_at_utc > '2026-05-28T20:30'
   AND endpoint_id LIKE 'daily-log%'
 ORDER BY started_at_utc;
```

```
daily-log-manpower               | live_apply | success | success | 0
daily-log-manpower               | live_apply | success | success | 0
daily-log-notes                  | live_apply | success | success | 0
daily-log-notes                  | live_apply | success | success | 0
daily-log-deliveries             | live_apply | success | success | 0
daily-log-deliveries             | live_apply | success | success | 0
daily-log-delays-review-routed   | live_apply | success | success | 0
daily-log-delays-review-routed   | live_apply | success | success | 0
daily-log-inspections            | live_apply | success | success | 0
daily-log-inspections            | live_apply | success | success | 0
```

Ten apply runs, all `success`, all daily-log section endpoints. The
DCR smoke run (state `transport_error`) does not appear because smoke
mode does not write sync-run rows.

## No-secret / no-raw-body attestation

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'daily-log%'
   AND (canonical_json_redacted LIKE '%Bearer %'
     OR canonical_json_redacted LIKE '%access_token%'
     OR canonical_json_redacted LIKE '%refresh_token%'
     OR canonical_json_redacted LIKE '%client_secret%');
```
Result: `0`.

```sql
SELECT COUNT(*) FROM procore_live_records
 WHERE endpoint_id LIKE 'daily-log%' AND raw_body_persisted != 0;
```
Result: `0`.

The hash-only invariant for notes and delays is unit-tested with the
synthetic secret marker `MUST_NEVER_APPEAR_IN_CANONICAL_STORAGE` in
`tests/test_procore_live_sync_verified_chain.py::test_daily_log_delays_persists_with_review_routing_and_hash_only_body`
and `…test_daily_log_notes_persists_with_review_required_and_hash_only_body`.
Both tests assert the marker does NOT appear in
`canonical_json_redacted` and that `note_summary` / `description_summary`
hash structures DO appear.

## Promotion outcomes

- `daily-log-manpower` → `live_verified=True`, reason `live_smoke_passed_2026-05-28:d0836094`.
- `daily-log-notes` → `live_verified=True`, reason `live_smoke_passed_2026-05-28:49cb933b` (review-routed; hash-only body summary).
- `daily-log-deliveries` → `live_verified=True`, reason `live_smoke_passed_2026-05-28:52f90d5b`.
- `daily-log-delays-review-routed` → `live_verified=True`, reason `live_smoke_passed_2026-05-28:d3c84564` (review + safety route).
- `daily-log-inspections` → new row, `live_verified=True`, reason `live_smoke_passed_2026-05-28:e3d4b3c4`.
- `daily-log-dcrs` → new row, `live_verified=False`, reason `live_smoke_failed_2026-05-28:http_404_at_/rest/v1.0/projects/{project_id}/dcrs`.

Verified-set count: 5 → **10**. Canonical registry size: 14 → **16**.
`_UNVERIFIED_IDS` parametrized fail-closed test count: 9 → 6 (removed the
four daily-log sections that promoted; added `daily-log-dcrs`).

## Verification (repeatable, post-commit)

```bash
# Confirm the 5 promoted sections still work end-to-end:
for s in manpower notes deliveries delays-review-routed inspections; do
  HB_PROCORE_LIVE=1 hb-assistant procore live sync \
    --project tropical --endpoint daily-log-$s \
    --apply --sqlite-only --max-pages 3 --max-items 100 \
    --confirm-live-get --json | python -c "import json,sys; d=json.load(sys.stdin); print('${s}:', d.get('state'))"
done

# Confirm dcrs continues to fail-closed (live_verified=False -> not_live_verified):
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint daily-log-dcrs \
  --apply --sqlite-only --max-pages 1 --max-items 1 \
  --confirm-live-get --json | python -c "import json,sys; d=json.load(sys.stdin); print('dcrs:', d.get('state'), d.get('reason_codes'))"

# Hash-only invariant unit tests:
python -m pytest -q tests/test_procore_live_sync_verified_chain.py -k daily_log
```

Acceptance:
- All five `live sync` invocations return `state=success`.
- The dcrs invocation returns `state=not_live_verified` with reason
  codes including `endpoint_unverified_for_live`.
- All three daily-log unit tests pass.

## Contract-drift backlog (updated)

| Endpoint              | Status                                                                                  |
| ---                   | ---                                                                                     |
| `meetings`            | v1.1 path resolves; v1.0 normalizer schema mismatch (Prompt 07 backlog).                |
| `meeting-topics`      | Awaiting `meetings` promotion to populate via parent N+1 (Prompt 07 backlog).            |
| `submittal-responses` | HTTP 404 at v1.0 child path (Prompt 05 backlog).                                         |
| `submittal-packages`  | HTTP 404 at v1.0 sibling path (Prompt 05 backlog).                                       |
| `daily-log-dcrs`      | HTTP 404 at `/rest/v1.0/projects/{project_id}/dcrs` (Prompt 08 backlog).                 |
