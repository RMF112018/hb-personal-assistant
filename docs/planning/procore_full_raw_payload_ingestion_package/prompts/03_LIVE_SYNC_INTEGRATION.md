# 03 — Live sync integration

## Objective

Wire the full raw payload persistence API into `run_live_sync()` so live endpoint sync writes full endpoint payload rows and matching structured rows.

## Target

`src/hb_assistant/procore/live_sync.py`

## Preserve guardrails

Do not weaken:

- `HB_PROCORE_LIVE=1`;
- mapped project check;
- `--apply`;
- `--sqlite-only`;
- `--confirm-live-get`;
- verified endpoint fail-closed posture;
- no external writeback.

## Integration point

At the point where live item payloads have been retrieved and before/alongside existing normalization/upsert:

1. call full raw persistence API for each live item;
2. pass endpoint id, project key, Procore project id, parent id, item payload, fetched timestamp, and capture/sync run id;
3. continue existing `procore_live_records` projection unless tests prove safe removal.

## Parent/child endpoints

Handle parent ids for N+1/child endpoints, including:

- line items;
- invoice items;
- meeting detail/topics;
- RFI/submittal responses;
- activities;
- budget detail rows/columns;
- RFQ/change-event children.

Do not fabricate parent IDs. If parent cannot be determined, record an honest reason.

## Receipt fields

Add receipt fields without exposing payload bodies:

- `raw_payload_rows_written`;
- `structured_rows_written`;
- `full_raw_persistence_enabled`;
- `source_quality`;
- `raw_procore_payload_persisted`;
- `skipped_due_to_higher_quality`;
- `raw_payload_body_emitted_to_stdout=false`;
- `external_writeback_performed=0`.

## Tests

Use fixture transport. Prove `run_live_sync()` writes:

- `procore_live_records` if still retained;
- `procore_endpoint_raw_payloads` from full item payload;
- matching `procore_raw_*` structured rows;
- no raw body in receipt/stdout.

## Evidence

Write `docs/evidence/procore_full_raw_payload_ingestion/04-live-sync-boundary.md` with endpoints tested, counts, hashes, field-name coverage, and no raw body emission proof.
