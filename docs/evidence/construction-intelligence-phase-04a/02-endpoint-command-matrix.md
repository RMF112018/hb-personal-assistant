# Phase 04A — Per-Endpoint Command Matrix

Canonical 14-endpoint command surface for `hb-assistant procore live sync`,
`procore live smoke`, and `procore live records count`. Sourced from
`src/hb_assistant/procore/endpoints.py`.

## Operator command template

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint <endpoint-id> \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

## Endpoint matrix

| Endpoint ID | Family | Live verified? | Legacy alias | Review default | Sensitivity | Normalizer / SQLite target |
| --- | --- | --- | --- | --- | --- | --- |
| `projects` | foundation | yes | — | no | low | `_normalize_project` → `procore_live_records` |
| `rfis` | rfis | yes | `list-rfis` | no | medium | `normalize_rfi` → `procore_live_records` |
| `rfi-responses` | rfis | no (fail-closed) | — | yes | medium | unverified — receipt only |
| `submittals` | submittals | yes | `list-submittals` | no | medium | `normalize_submittal` → `procore_live_records` |
| `submittal-responses` | submittals | no (fail-closed) | — | yes | medium | unverified — receipt only |
| `submittal-packages` | submittals | no (fail-closed) | — | no | medium | unverified — receipt only |
| `observations` | observations | no (fail-closed) | `list-observations` | yes | high | unverified — receipt only |
| `meetings` | meetings | yes | `list-meetings` | no | medium | `normalize_meeting` → `procore_live_records` |
| `meeting-topics` | meetings | no (fail-closed) | `list-meeting-topics` | yes | medium | unverified — receipt only |
| `daily-log-weather` | daily_logs | yes | — | no | low | `_normalize_daily_log_weather` → `procore_live_records` |
| `daily-log-manpower` | daily_logs | no (fail-closed) | — | no | low | unverified — receipt only |
| `daily-log-notes` | daily_logs | no (fail-closed) | — | yes | high | unverified — receipt only |
| `daily-log-deliveries` | daily_logs | no (fail-closed) | — | no | medium | unverified — receipt only |
| `daily-log-delays-review-routed` | daily_logs | no (fail-closed) | — | yes | critical | unverified — receipt only |

## Verified-row behavior

The 5 `live_verified=true` rows execute the full chain (gate -> GET ->
pagination -> normalize -> upsert -> watermark -> receipt). End-to-end fake
transport tests cover the RFI path; the same orchestrator code drives every
verified endpoint.

## Unverified-row behavior

The 9 `live_verified=false` rows are command-visible (listed by
`procore live endpoints list`) and accept their CLI command, but:

- No live HTTP is issued (transport never invoked — proved by the
  `_default_live_transport` boom-trap in `tests/test_procore_live_sync_unverified_fail_closed.py`).
- No row is written to `procore_live_records`.
- The receipt returns `state="not_live_verified"`,
  `no_live_call_performed=true`, and `reason_codes` includes
  `endpoint_unverified_for_live` plus the adapter's `verification_reason`.

Promotion of an unverified row to verified requires a future Prompt 03 live
smoke run that proves docs + tenant scope; flipping `live_verified` to `true`
in `endpoints.py` then activates the chain without further code change.

## Stop-condition assertions

- Every receipt carries `raw_body_persisted=false` and `secrets_redacted=true`.
- `procore_live_records.raw_body_persisted` and
  `procore_live_sync_runs.raw_body_persisted` schema-level `CHECK (= 0)`
  constraints reject any insert attempting to flip the bit.
- `procore_live_sync_runs.redaction_applied` `CHECK (= 1)` rejects any sync
  run claiming to skip redaction.
- `ProcoreHTTPClient._require_get` rejects any non-GET method at runtime.
