# Email + Calendar Raw → Structured Projection Layer (V49)

## Purpose

Turn the private local SQLite DB into a useful system of record for email/calendar by capturing
full raw business content under policy and projecting it into a queryable **final structured
projection layer** — while keeping every outbound surface redacted. Mirrors the Procore
V46/V47/V48 raw-landing → structured-projection discipline.

## Layers

```
Graph (read-only)
  └─ raw landing (V42, hardened V49): email_message_raw_content / email_thread_raw_context /
        calendar_event_raw_content  — full bodies + source_quality + payload_hash + provenance
        + lossless raw_sidecar_json (join URL kept only here under join_url_policy)
        └─ projection engine (registry-driven, idempotent, precedence-aware, fail-closed)
             └─ structured projection (V49):
                  email_raw_message_structured (+recipients, +attachments)
                  email_raw_thread_structured  (+messages)
                  calendar_raw_event_structured (+attendees, +recurrence, +locations)
                  + *_projection_runs / *_projection_coverage / *_raw_ingestion_runs receipts
                  └─ consumer read models (precedence-aware): endpoints, meeting prep,
                       model-context packets, follow-up windows, relationship extraction, retrieval
```

## Key components (`src/hb_assistant/construction/email_calendar/`)

- `projection_registry.py` — committed allow-list mapping every raw scalar column + nested JSON
  path to one destination (primary column / child table / lossless sidecar / explicit exclusion).
- `schema.py` — registry-derived DDL (`build_v49_ddl`) + additive column reconcile; consumed by the
  V49 migration. Guarantees DDL ↔ engine column parity.
- `projection_engine.py` — projects raw rows → structured parent/child rows; idempotent (parent
  upsert + child delete/reinsert); source-quality precedence (no downgrade); fails closed on any
  unmapped business path; receipts carry counts/field-names only. `inventory`/`coverage`/`status`/
  `reprocess`.
- `projection_matrix.py` — mechanical completeness gate (unmapped primary/nested counts).
- `source_quality.py` — precedence ladder (`graph_full_body`/`graph_full_event_body` > preview >
  redacted_legacy > metadata_only) + a SQL `CASE` used for data-layer downgrade prevention.
- `read_models.py` — precedence-aware consumer selectors returning `selected_source` +
  `source_quality` + redacted-safe fields + a `body_ref` (local-private body via audited `load_body`).
- `redaction.py` — email/calendar no-leak scanner (Graph/Teams/Outlook tokens + join URLs + sentinels).

## Invariants

- Additive-only migration (V49); V1–V48 untouched; idempotent; unconditional reconcile self-heals
  column drift.
- Body text lives only in the raw tables; structured rows carry availability flags + a raw link.
  The calendar join URL lives only in the raw `join_url` column under `join_url_policy`; structured
  rows carry a `has_join_url` flag.
- Every structured + receipt table has SQLite CHECK guards `raw_body_emitted_to_evidence = 0` and
  `external_writeback_performed = 0`.
- Consumers prefer the structured layer by source-quality rank; a lower-quality row cannot downgrade
  consumer context; raw reads are audited in `raw_content_access_events`.

## Nested-field mapping (dotted `item_fields`)

Child arrays map nested object leaves with dotted source paths in the registry's `item_fields`
(e.g. `recurrence`: `pattern.type → pattern_type`, `range.startDate → range_start`). The
completeness matrix flattens every observed JSON path, so a declared **container** key alone does
not cover its leaves — each leaf must be declared and mapped or it is `unmapped` and the gate fails
closed. The calendar `locations[]` child array maps the seven Microsoft Graph location leaves to
dedicated columns:

```text
address.street → address_street    address.city → address_city    address.state → address_state
address.countryOrRegion → address_country_or_region    address.postalCode → address_postal_code
coordinates.latitude → coordinates_latitude    coordinates.longitude → coordinates_longitude
```

Because the DDL is generated from the registry and the V49 reconcile runs unconditionally, adding
these `item_fields` is sufficient: fresh DBs get the columns from `CREATE TABLE`; existing V49 DBs
get them via additive `ALTER TABLE ADD COLUMN`. The lossless `raw_sidecar_json` and the join-URL
policy are unaffected. Evidence: `docs/evidence/email-calendar-full-raw-content-ingestion/04E_locations_nested_field_remediation.md`.

## CLI

`hb-assistant email-calendar raw {projection-inventory, projection-coverage, projection-reprocess,
status, no-raw-leak-scan}` — SQLite-only, no Graph calls; `projection-reprocess` is dry-run by
default and refuses `--apply` without an explicit `--db`.

## Commits

- Pass 1 `3e50fd7e` — schema + ingestion + projection engine + fixtures + /tmp proof.
- Pass 2 — consumer read models + CLI + redaction/access audit + evidence + runbook + this doc.
- Pass 3 — calendar `locations[]` `address.*` / `coordinates.*` nested-leaf mapping (registry +
  engine); resolved a live prod-copy gate failure (7 unmapped leaves → 0). See evidence 04E.
