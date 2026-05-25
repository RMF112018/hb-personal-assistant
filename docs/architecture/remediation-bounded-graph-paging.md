# Remediation: Bounded Graph Paging (Prompt 07)

## Summary

Prompt 07 adds deterministic, bounded paging across Graph read clients to prevent silent first-page truncation.

## Contract

- Graph paging now supports explicit bounds:
  - `max_items`
  - `max_pages`
- Stop conditions are deterministic:
  1. item cap reached
  2. page cap reached
  3. no `@odata.nextLink`

## Config Controls

- `mail.max_items_per_run`
- `calendar.max_items_per_run`
- `files.max_drive_items_per_run`
- `graph.max_pages_per_call`

## Affected Runtime Paths

- Mail: inbound and sent listing
- Calendar: `calendarView` listing
- Drive: children listing and message attachment metadata listing

## Verification

Tests cover both mocked `@odata.nextLink` bounds and client cap wiring. Runtime diagnostics remain environment-dependent and can fail if local application-support path permissions are restricted.
