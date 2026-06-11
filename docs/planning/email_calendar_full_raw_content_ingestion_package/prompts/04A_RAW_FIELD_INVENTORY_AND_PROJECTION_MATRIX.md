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

# 04A — Raw Field Inventory and Projection Matrix

## Objective

Create a mechanical inventory of every available raw email/calendar content field and a projection matrix that maps every observed primary and nested business field path to a final structured projection destination.

This prompt is mandatory. Do not proceed to consumer work until the matrix exists and shows no unmapped business field paths for fixture payloads.

## Scope

Inventory both existing and newly captured raw local content:

- `email_message_raw_content`
- `email_thread_raw_context`
- `calendar_event_raw_content`
- any new raw landing table introduced by this package
- JSON columns inside those rows, including:
  - `to_recipients_json`
  - `cc_recipients_json`
  - `bcc_recipients_json`
  - `attachment_metadata_json`
  - `messages_json`
  - `attendees_json`
  - `recurrence_json`
  - any future sidecar JSON columns used for raw content preservation

## Required matrix columns

At minimum:

```text
source_family
source_table
raw_column_or_json_path
observed_type
cardinality
occurrence_count
non_null_count
empty_count
business_category
destination_kind
destination_table
destination_column
child_table_parent_key
extraction_strategy
exclusion_reason
status
```

## Destination kinds

Allowed destination kinds:

- `primary_column`
- `child_table_column`
- `dimension_table_column`
- `bridge_table_column`
- `lossless_sidecar_json`
- `excluded_non_business`
- `excluded_transport_secret`
- `excluded_policy_blocked`

Business content may not be excluded merely because it is inconvenient, nested, variable-shaped, or low frequency.

## Email field coverage requirements

Every available raw email field must be mapped, including:

- identifiers and source refs: message hash/ref, conversation/thread hash/ref, internet-message hash/ref, source refs, project refs, folder/source refs;
- subject and preview/body text/body HTML;
- sender/from display and address information;
- to/cc/bcc recipient arrays, including display/name/address/domain/role where available;
- sent, received, last-modified, captured, and source-updated timestamps;
- importance, categories, sensitivity, flags, and follow-up metadata if available;
- attachments metadata arrays: attachment id/hash, name, content type, size, inline flag, linked drive-item hints, sensitivity hints, URL/token exclusion status;
- thread rollups: message order, participant count/list, latest/first timestamps, thread subject, source refs, body availability, source-quality rollups.

## Calendar field coverage requirements

Every available raw calendar field must be mapped, including:

- graph event hash/ref, iCal UID hash/ref, series/master refs, source refs, project refs;
- subject, body text/body HTML, preview if available;
- organizer name/address/domain and attendee arrays with type/status/name/address/domain;
- start/end/date/timezone fields, all-day flags, recurrence pattern/range, cancellation, private/sensitivity, categories;
- location and locations arrays, online meeting provider, join URL policy status, web link hash/ref;
- created/last-modified/original-start/transaction/idempotency timestamps where available;
- meeting-prep rollups: agenda/body availability, attendee roles, unresolved attendees, event-to-thread/document/procore relationship refs.

## Completion gate

For every source family with available raw rows or synthetic fixture raw rows:

- `unmapped_primary_business_fields = 0`
- `unmapped_nested_business_fields = 0`
- no observed nested array without either a child table or a documented lossless sidecar
- no high-value business field hidden solely in generic JSON when it deserves a named queryable column
- exclusions have explicit `exclusion_reason`
- fixture tests fail when a new business JSON path is observed but not mapped

## Evidence

Write:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/04A_raw_field_inventory.md
docs/evidence/email-calendar-full-raw-content-ingestion/04A_projection_matrix_summary.md
docs/evidence/email-calendar-full-raw-content-ingestion/email_calendar_projection_matrix.csv
```

Evidence may include field names, JSON paths, counts, table names, null rates, hashes, and redacted examples only.
