# No-live-call / no-writeback proof

This remediation touches only local extraction logic. It introduces no Procore, Graph, email,
calendar, SharePoint, OneDrive, or MCP calls, and no external writeback.

- `backfill_from_live_records(apply=True)` receipt reports `live_procore_calls=0` and
  `external_writeback_performed=0` (see `db-copy-backfill-proof.md`).
- The module imports no Procore HTTP client; a separate repo test enforces the client's absence
  for non-live work.
- The structured-analytics V46 tables carry `CHECK(external_writeback_performed = 0)` and
  `CHECK(raw_payload_emitted_to_* = 0)` constraints (unchanged).
- Unit tests assert the local-only posture:
  - `test_backfill_populates_invoice_item_amount_from_real_fields` asserts
    `live_procore_calls == 0` and `external_writeback_performed == 0`;
  - `test_cli_contract_and_reprocess_are_local_only` (pre-existing) asserts
    `live_procore_calls == 0` and `guardrails.writeback == "none"`.
- Source data was read from `procore_live_records` (a local legacy projection); the only writes
  were to a disposable `/tmp` copy.
