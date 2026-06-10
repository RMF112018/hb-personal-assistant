# 04 — Live sync boundary

Test: `run_live_sync(project_key="tropical", endpoint="rfis", apply, sqlite_only,
confirm_live_get)` driven by a fixture transport returning 2 full RFI items (one carrying
a synthetic `access_token`).

## Raw-first ordering

For each retrieved item (main loop and inline N+1 children), `run_live_sync` resolves a
stable `record_id` + parent id and calls `upsert_full_raw_payload_and_structured(...)`
**before** `upsert_procore_live_record(...)`, history, and `project_*` enrichment.

Proof (`test_raw_persisted_before_live_record_projection`): with
`upsert_procore_live_record` monkeypatched to raise, the full raw payload still landed —
`procore_endpoint_raw_payloads` had **2 persisted rows** while `procore_live_records`
had **0**.

## Receipt fields (no payload body)

| field | value |
|---|---|
| full_raw_persistence_enabled | true |
| raw_payload_rows_written | 2 |
| structured_rows_written | 2 |
| raw_persist_error_count | 0 |
| raw_payload_body_emitted_to_stdout | false |
| raw_body_persisted | false |
| ok | true |

`json.dumps(receipt)` contains neither the RFI subject (`Door schedule clarification`)
nor the synthetic token — no body leaks into the receipt.

## DB rows written

`procore_endpoint_raw_payloads` (endpoint `rfis`): 2 rows, `source_quality=live_full_payload`,
`raw_procore_payload_persisted=1`, synthetic `access_token` absent from `payload_json`.
`procore_raw_rfis`: 2 structured rows.

## Verdict downgrade on failure

`test_raw_persist_failure_degrades_run_verdict`: with the full-raw API forced to raise,
the run continues per-item (isolation) but `raw_persist_error_count=2`, `ok=false`,
`state="degraded_raw_persistence"`.

## Guardrails preserved

`HB_PROCORE_LIVE`, mapped project, `--apply`, `--sqlite-only`, `--confirm-live-get`,
verified-endpoint fail-closed, no external writeback — all existing live-sync chain tests
(verified / phase05 / N+1, 45 tests) still pass.

## Parent/child endpoints

Parent ids resolved without fabrication: activities→`schedule_id`,
inspection-items→`list_id`, generalized N+1 children→tagged `_PARENT_ID_KEY` (stripped
from the stored payload). Inline children (RFI replies, submittal responses, meeting
topics) persist with `parent_procore_id = parent record id`.
