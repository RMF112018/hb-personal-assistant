# Local Data Model and Source-Link Registry

Prepared: 2026-05-25

## SQLite Rules

- SQLite canonical store under Application Support.
- Enable `foreign_keys`, WAL, transactions, and migrations.
- Every email/event/attachment/file/note/parser output becomes or links to a `source_record`.
- Upsert by `source_type + source_key`.
- Generated outputs cannot persist without source links.

## Core Tables

| Table | Purpose |
| --- | --- |
| source_records | Universal source identity, source system, URL, external IDs, hashes, status. |
| emails | Mail metadata and body-check indicators. |
| calendar_events | Event metadata for calendarView window. |
| attachments | Attachment metadata linked to parent source. |
| files | driveItem/file metadata, cache path, hash, download/parse status. |
| parser_outputs | Bounded extraction metadata and excerpts. |
| action_items | Source-linked actions/prep/waiting/file-review records. |
| source_links | Relationships among sources, actions, parser outputs, and notes. |
| assistant_runs | Run ledger for idempotency and catch-up-after-wake. |
| sync_state | Per-source cursors and last success state. |

## Source Keys

| Source Type | Key Pattern |
| --- | --- |
| email | graph:mail:{immutable_or_id} |
| calendar_event | graph:event:{ical_uid_or_id}:{start} |
| attachment | graph:attachment:{parent_id}:{attachment_id} |
| drive_item | graph:drive-item:{drive_id}:{item_id} |
| obsidian_note | obsidian:note:{vault_relative_path} |
| cached_file | cache:file:sha256:{hash} |

See `resources/sqlite-schema.sql`.
