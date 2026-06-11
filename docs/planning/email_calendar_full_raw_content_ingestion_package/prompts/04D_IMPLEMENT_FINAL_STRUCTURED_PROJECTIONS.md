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

# 04D — Implement Final Structured Projections for All Available Raw Content

## Objective

Populate the final structured projection tables for every available raw email/calendar row. This is the decisive implementation prompt.

Do not mark this package complete because raw rows exist. Completion requires that the final structured projections are populated and mechanically proven complete.

## Required projection coverage

### Email

For every row in `email_message_raw_content` with available content:

- one parent structured message projection row;
- zero or more recipient child rows for to/cc/bcc/from;
- zero or more attachment metadata child rows;
- linkage to the source raw row;
- source-quality classification;
- projection version/hash;
- queryable content availability flags;
- project/source/thread refs where available.

For every row in `email_thread_raw_context` with available content:

- one parent structured thread projection row;
- child/message refs or lossless message sidecar;
- participant/source-quality/body-coverage rollups;
- source refs and project refs;
- relationship-ready fields for local model, daily brief, and follow-up agents.

### Calendar

For every row in `calendar_event_raw_content` with available content:

- one parent structured event projection row;
- attendee child rows;
- recurrence detail rows or mapped lossless sidecar;
- location/online-meeting detail rows or mapped lossless sidecar;
- meeting-context projection suitable for agenda/meeting prep;
- linkage to the source raw row;
- source-quality classification;
- projection version/hash;
- queryable content availability flags;
- project/source refs where available.

## Source families with no raw rows

If Bobby's current `/tmp` DB copy does not yet have raw rows for a family, use synthetic fixtures to prove the implementation and mark DB-copy evidence as:

```text
no_raw_rows_available_in_current_copy
```

Do not claim production completeness for a source family that has no raw rows. Claim implementation readiness with fixture proof and a production runbook.

## Required proof per source family

For each source family with available raw rows:

- raw parent count;
- projected parent count;
- child row counts for every nested array;
- source-quality distribution;
- null-rate matrix for high-value fields;
- unmapped primary business fields count;
- unmapped nested business fields count;
- downgrade-prevention proof;
- no-leak proof.

## Required status semantics

Projection coverage output must distinguish:

- `complete`
- `complete_with_policy_exclusions`
- `no_raw_rows_available_in_current_copy`
- `blocked_by_policy`
- `blocked_by_missing_source_data`
- `failed_unmapped_fields`

Only `complete` or `complete_with_policy_exclusions` may satisfy the package completion gate for source families with raw rows.

## Evidence

Write:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/04D_final_structured_projection_coverage.md
docs/evidence/email-calendar-full-raw-content-ingestion/04D_projection_row_count_matrix.md
docs/evidence/email-calendar-full-raw-content-ingestion/04D_projection_null_rate_matrix.md
docs/evidence/email-calendar-full-raw-content-ingestion/04D_unmapped_field_report.md
```
