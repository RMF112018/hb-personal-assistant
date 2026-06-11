# Pass 1 Checkpoint — Email + Calendar Full Raw Content → Structured Projection

Pass 1 delivers the additive schema, raw-ingestion hardening, and the final structured
projection layer + completeness proof. **Pass 2 (consumers, daily brief / model context,
meeting prep, CLI/status surfaces, full evidence bundle, operator runbook, architecture docs)
is deferred pending Bobby's review of this checkpoint.** No production ingest apply was run; no
production DB was mutated.

## What landed (commit #1)

- **Migration V49** (`store/migrator.py`) — additive only; schema head 48 → 49; idempotent.
  - source-quality / provenance columns + lossless `raw_sidecar_json` on the three V42 raw tables;
  - registry-derived structured parent/child projection tables (mirrors Procore V47 `build_v47_ddl`);
  - ingestion-run / projection-run / coverage / source-quality-snapshot receipt tables;
  - unconditional curated-column reconcile (mirrors V48).
- **Ingestion hardening** (`construction/store/repositories.py`, `construction/email/message_indexer.py`,
  `construction/calendar/event_indexer.py`, `graph/calendar_readonly_client.py`):
  - raw upserts classify `source_quality`, compute `payload_hash`, and enforce **data-layer
    downgrade prevention** (a lower-quality re-capture never erases local-private body content);
  - new `record_raw_content_access_event(...)` writer (the V42 audit table had no writer) +
    `record_email_calendar_raw_ingestion_run(...)` receipt writer; both wired into the indexers;
  - calendar `get_event` `$select` widened; extra Graph fields preserved losslessly in
    `raw_sidecar_json` with the join URL scrubbed out.
- **Projection layer** (`construction/email_calendar/`): `source_quality`, `projection_registry`
  (committed allow-list), `projection_matrix` (mechanical completeness gate), `projection_engine`
  (registry-driven, idempotent, precedence-aware, fail-closed on unmapped, no-raw receipts),
  `schema` (registry-derived DDL + reconcile).
- **Tests** (3 modules, 32 tests, all green) + the Procore schema-head assertion bumped to 49.

## Completeness proof (the package's central acceptance gate)

On a `/tmp` copy of the **real production DB** (117 calendar + 1 email raw rows):

```text
unmapped_primary_business_fields = 0   (every source family with raw rows)
unmapped_nested_business_fields  = 0   (every source family with raw rows)
calendar_event: 117 raw -> 117 structured parents + 1262 attendee child rows
email_message:    1 raw ->   1 structured parent  + 2 child rows
email_thread:     0 raw -> no_raw_rows_available_in_current_copy (honest)
production DB sha256/mtime: UNCHANGED
```

## Safety attestations (Pass 1)

```text
production_db_mutated:        no  (sha256 + mtime unchanged; /tmp copy only)
production_ingest_apply_run:  no
graph_writes:                 none (read-only clients; $select widened only)
raw_bodies/join_urls/tokens in evidence/logs/CLI/handoff: none (no-leak scan: 0 findings)
secrets/tokens stored:        none
migration:                    additive only (V1-V48 untouched; idempotent)
```

## Deferred to Pass 2 (do NOT start until Bobby approves)

consumer read-models (daily brief follow-ups, meeting prep, model-context packets, relationship
extraction, retrieval) wired to the structured layer with source-quality precedence; the
`hb-assistant email-calendar raw` CLI group; outbound redaction/access-audit prompt 06; full
evidence bundle (02/03/04/05/06/07/08); operator production runbook; architecture docs.
