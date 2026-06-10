# 03 Capture Runs And Raw Payload Landing

V46 adds local-only capture/control tables and governed raw landing:

- `procore_endpoint_contracts`
- `procore_endpoint_capture_runs`
- `procore_endpoint_capture_pages`
- `procore_endpoint_capture_errors`
- `procore_endpoint_raw_payloads`

The copied-DB validation populated `30,059` raw landing rows from existing local
`procore_live_records`, labelled `source_quality=redacted_legacy_projection`.
