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

# 04C — Projection Registry and Extractors

## Objective

Implement a deterministic projection registry and extractor layer that maps raw email/calendar row fields and JSON paths into final structured projection tables.

The extractor is the enforcement point for projection completeness. It must be testable without live Graph access.

## Required functionality

- Register field-path mapping plans for:
  - raw email messages;
  - raw email threads;
  - raw calendar events;
  - email recipients arrays;
  - email attachment metadata arrays;
  - calendar attendee arrays;
  - calendar recurrence objects;
  - calendar locations/online meeting objects where present.
- Extract scalar fields to primary structured rows.
- Expand nested arrays to child rows.
- Expand nested objects to child/detail/dimension rows or documented lossless sidecars.
- Preserve raw row linkage and source-quality.
- Preserve idempotency.
- Avoid raw value emission in logs/receipts/evidence.
- Make coverage failures loud and mechanical.

## Field handling rules

- Date/time fields normalize to UTC string where possible and retain original timezone/source timezone where useful.
- Email addresses may be local-private in DB if policy permits, but evidence/status output must hash or redact them.
- Subjects and bodies may be local-private in designated DB tables if policy permits, but outbound surfaces must redact or summarize.
- HTML bodies should preserve original HTML locally where policy allows and may derive plaintext into a separate field with provenance marker.
- Attachment URLs, signed URLs, tokenized links, auth headers, OAuth tokens, and join URLs must have explicit policy handling. Join URLs may be local-private only when policy allows and must never appear in evidence.
- Recurrence must not be discarded. If not fully normalized, persist a lossless sidecar and mark every recurrence path as mapped.
- Variable custom/extension fields must map to a sidecar only when named columns would be brittle; the matrix must document the sidecar path.

## Required CLI or internal surfaces

Add or extend safe local commands/functions equivalent to:

```text
email-calendar raw projection-inventory --db <copy> --json
email-calendar raw projection-reprocess --db <copy> --apply --json
email-calendar raw projection-coverage --db <copy> --json
```

Use existing CLI conventions if names differ, but the functionality must exist and be documented.

## Completion gate

A new fixture-based test must fail when:

- a top-level raw column is not included in the projection matrix;
- a nested JSON path is not included in the projection matrix;
- a business path is mapped to neither named structured column, child table, bridge, dimension, nor documented lossless sidecar;
- an exclusion lacks an explicit reason.

## Evidence

Write:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/04C_projection_registry_and_extractors.md
```
