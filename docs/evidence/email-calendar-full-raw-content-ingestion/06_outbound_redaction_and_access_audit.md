# 06 — Outbound Redaction and Access Audit

## No-leak scanner

`construction/email_calendar/redaction.py::no_raw_leak_scan` extends the Procore pattern set with
Microsoft 365 / Graph / Teams / Outlook shapes and optional caller sentinels. It emits matched
**pattern names + counts only** (never matched text). The pattern set covers: OAuth bearer-token
authorization values, access/refresh credential tokens, client secrets, authorization headers,
Graph attachment download URLs, Teams meeting join URLs, Outlook safelink URLs, Skype join URLs,
raw HTML bodies, and any caller-supplied body/agenda sentinel. (The exact regex pattern names are
defined in the module; they are not reproduced here so this evidence file itself stays scan-clean.)

Exposed as `hb-assistant email-calendar raw no-raw-leak-scan --path … [--sentinel …]` (exit 3 on
any finding).

## Access audit

- `raw_content_access_events` has a writer (`record_raw_content_access_event`) wired into the
  email/calendar indexers (raw persist) and the read-model `load_body(...)` accessors (raw read).
- Tests: `test_raw_access_event_recorded`, `test_load_body_returns_local_private_and_audits`.

## Outbound surfaces emit counts / names only

- Projection receipts, coverage, status, inventory carry counts + field names + source-quality
  only (engine receipts are value-free).
- Structured + receipt tables carry the SQLite-enforced guards `raw_body_emitted_to_evidence = 0`
  and `external_writeback_performed = 0`.
- Model-context packets store no raw prompt/response.

## No-leak proof

```text
scan target:        docs/evidence/email-calendar-full-raw-content-ingestion/  (+ captured CLI output)
patterns scanned:   oauth/secret/graph-download/teams-join/outlook-safelink/html + body/agenda sentinels
unsafe_finding_count: 0
verdict:            PASS
```

Tests: `test_no_leak_scan_zero_on_clean_evidence`, `test_outbound_serializers_do_not_emit_raw_body`,
`test_read_model_objects_carry_no_body_or_join_url`, `test_retrieval_structured_is_redacted`.
