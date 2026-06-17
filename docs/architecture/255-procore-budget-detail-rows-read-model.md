# 255 - Procore Budget Detail Rows Read Model

## Summary

This run adds an endpoint-specific Procore Budget Detail Rows read model for
forecasting. The authoritative local path is:

`procore_endpoint_raw_payloads` -> `procore_ep_budget_detail_columns` ->
`procore_ep_budget_detail_rows` -> `procore_ep_budget_detail_row_cells` ->
`construction-financial-review` read-only accessor.

The existing `procore_financial_budget_rows`, `procore_financial_amount_facts`,
and `procore_raw_budget_rows` projections remain unchanged. They are not promoted
to the forecasting source of truth for full Budget Detail Rows payload data.

## Local DB Contract

- Full Procore business payloads are stored only in the local SQLite raw landing
  table after transport-secret scrubbing.
- The read model stores queryable scalar fields, hashes, IDs, timestamps, and
  dynamic cell values needed by forecasting.
- Receipts, committed evidence, docs, and tests must remain body-free: counts,
  hashes, field names, and summaries only.
- The read model requires `live_full_payload` rows for authoritative forecasting;
  redacted legacy projections cannot overwrite live full projections.

## Command

Dry-run, zero local DB writes:

```bash
hb-assistant procore live seed-budget-details --project tropical --dry-run --read-only-procore --no-procore-writeback --json
```

Apply to local SQLite:

```bash
hb-assistant procore live seed-budget-details --project tropical --apply-local-db --read-only-procore --no-procore-writeback --confirm-live-get --json
```

The receipt reports `live_procore_get_performed`, `local_db_write_performed`,
and `external_writeback_performed` separately. It also reports budget-view
selection mode, seeded view IDs, target-code view IDs, endpoint GET counts, and
pagination exhaustion status.

## Forecast Access

`construction-financial-review` reads the new tables with SQLite `mode=ro`.
The accessor returns row lineage, raw payload IDs, payload hashes, timestamps,
common amount fields, and dynamic cells. It does not select or return raw
payload JSON bodies.

The parity command compares DB-backed Budget Detail Rows against the configured
Tropical forecast context package:

```bash
python -m construction_financial_review.cli procore-budget-details-parity --project tropical
```

CostEntries/Sage-derived actuals remain accounting truth. Budget Detail ERP
job-to-date fields are supporting evidence and cross-check fields.
