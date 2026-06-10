# 242 — Scheduled Procore Full Pipeline Refresh

## Behavior

The production `daily-source-refresh` scheduler runs at `20:00` local time and passes
`RefreshOptions.procore_project_scope` / `procore_project_keys` into
`SourceRefreshOrchestrator`. Production configuration must set:

```yaml
automation:
  scheduler:
    procore_project_scope: "all_mapped"
    procore_project_keys: []
```

`all_mapped` includes every Procore registry row whose status is live-refresh eligible.
The eligible statuses are exactly `pilot` and `active`. `pending`, `deprecated`,
missing-ID, unknown, and allowlist-excluded projects are never refreshed silently; they
are emitted in the receipt with reason codes. If `procore_project_keys` contains an
unknown or unsafe key, the run blocks before live Procore reads.

## Pipeline

When production scheduler live reads are enabled, Procore remains GET-only behind
`HB_PROCORE_LIVE=1` and local SQLite is the only mutation target. After the canonical
`procore_live_*` refresh, the orchestrator runs the in-process projection pipeline:

1. Verify current-run `live_full_payload` rows in `procore_endpoint_raw_payloads`.
2. Run `SQLiteMigrator.apply()` for V48 projection schema reconciliation.
3. Run `projection_schema_audit`.
4. Run endpoint-specific projection replay with `MODE_ENFORCE`.
5. Run `projection_audit`.

Projection replay is skipped and the scheduled run is marked degraded if raw full-payload
freshness is missing or schema parity is broken. Projection replay or audit failures are
never hidden behind a green scheduler status.

## Receipt

The scheduler receipt includes `procore_projection_summary` with:

- selected and skipped project counts plus per-project reason metadata;
- `raw_full_rows_by_project` and `raw_full_rows_by_project_endpoint`;
- projection schema audit ok/mismatch counts;
- projection replay ok and primary/child row counts;
- projection audit ok, unknown business field count, and runtime schema mismatch count;
- guardrails showing no live projection calls, no external writeback, and no emitted values.

Receipts and evidence are metadata-only: no raw payload values, tokens, signed URLs, or
source-system writeback are emitted.

## Operator Inspection

Inspect the last scheduled receipt with:

```bash
hb-assistant scheduler status daily-source-refresh --environment production --json
```
