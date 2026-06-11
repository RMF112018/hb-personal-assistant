You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.
- Raw capture is not completion. Completion requires final structured projection coverage of all available raw email/calendar content fields.

# 04B — Final Structured Projection Schema

## Objective

Design and implement additive local SQLite tables that make the captured raw email/calendar content queryable without requiring normal consumers to spelunk raw JSON or raw body blobs.

The final structured projection tables are the acceptance target for this package. Raw landing tables alone are insufficient.

## Required implementation shape

Implement an additive migration after the observed schema head, expected V47 unless repo head has advanced. Preserve all existing legacy and raw tables.

The exact names may follow repo conventions, but the schema must include the following logical projections:

### Email projections

- message-level structured projection table
- thread-level structured projection table
- recipient child/detail table
- attachment metadata child/detail table
- message-to-thread bridge if needed
- source-quality / projection-run receipt table
- field-inventory / projection-matrix / coverage result tables, unless coverage is fully emitted through CLI plus evidence

Required queryable columns include:

- source identifiers/hashes/refs
- project/source refs
- subject/body availability flags
- body text/body HTML local-private content or a clearly linked local raw-content ref, depending on policy
- sender/from fields
- sent/received/source-updated/captured timestamps
- source-quality and precedence fields
- security scrub status
- raw row linkage
- projection schema version
- idempotency key/hash

### Calendar projections

- event-level structured projection table
- attendee child/detail table
- recurrence child/detail table or lossless recurrence sidecar with mapped field paths
- location/online-meeting detail table if variable shape requires it
- meeting-context projection table suitable for meeting prep
- source-quality / projection-run receipt table
- field-inventory / projection-matrix / coverage result tables, unless coverage is fully emitted through CLI plus evidence

Required queryable columns include:

- source identifiers/hashes/refs
- project/source refs
- subject/body availability flags
- body text/body HTML local-private content or a clearly linked local raw-content ref, depending on policy
- organizer fields
- start/end/timezone/all-day/cancelled/private/sensitivity/category fields
- join URL policy status and local-private link/ref handling
- recurrence fields
- source-quality and precedence fields
- security scrub status
- raw row linkage
- projection schema version
- idempotency key/hash

## Local-private raw content rule

It is acceptable for the private SQLite DB to store raw email/calendar business content in designated local-private raw/structured tables when policy permits it. It is not acceptable for that content to leak to:

- evidence;
- committed fixtures;
- stdout;
- logs;
- browser/status JSON;
- Obsidian;
- daily brief output;
- raw model prompt/response receipts.

## Source-quality precedence

Implement deterministic precedence so that higher-quality rows win:

1. `graph_full_body` / `graph_full_event_body`
2. `graph_body_preview_only`
3. `redacted_legacy_projection`
4. `metadata_only`

A lower-quality projection must not overwrite higher-quality local-private fields. A newer lower-quality record may update metadata such as `last_seen` or source refs, but may not erase full body/event content.

## Required tests

Add tests proving:

- migrations are idempotent;
- all new tables have guard columns appropriate to outbound leak prevention;
- child tables are populated from nested arrays;
- source-quality precedence prevents downgrades;
- raw row linkage exists for every projected row;
- synthetic fixtures with nested fields project to named columns/child tables/sidecars;
- fixture coverage fails on any unmapped business JSON path.

## Evidence

Write:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/04B_structured_projection_schema.md
```
