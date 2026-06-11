You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 04 — Thread and Meeting Context Projection

## Objective

Build durable, raw-aware but outward-safe projections that make raw email threads and raw calendar events useful for daily brief, meeting prep, relationship extraction, and retrieval.

## Email thread projection

Update thread context construction so it is built from persisted `email_message_raw_content` rows, not only the transient in-memory message batch.

Requirements:

- Group by conversation/thread ID where available; fallback to deterministic thread key.
- Include ordered message summaries with body_text/body_html references or bounded content as policy allows.
- Store full useful raw context locally in `email_thread_raw_context`.
- Add source quality based on member messages:
  - `graph_full_body` if at least one useful full body is present and thread context includes it;
  - `graph_body_preview_only` if previews only;
  - `metadata_only` if no body/preview.
- Preserve source refs and project links.
- Never emit thread raw content in logs/evidence/stdout.

## Calendar meeting context projection

Build meeting-prep inputs from `calendar_event_raw_content` plus linked emails/documents/Procore records.

Requirements:

- Use event body/agenda, attendees, organizer, recurrence, and time details.
- Generate redacted meeting-prep sections by default.
- Preserve raw agenda/body only inside DB raw tables or explicit model packets.
- Include source refs and evidence trails.
- Record raw access events.

## Tests

- Thread projection uses persisted full raw body rows after process restart.
- Meeting-prep projection uses persisted raw event body/attendees after process restart.
- Redacted output does not include synthetic raw content.
- Missing raw rows produce honest degraded/metadata-only status.

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/04_thread_and_meeting_context_projection.md
```

## Structured projection dependency

This prompt must consume the final structured projection layer produced by `04A`–`04D`. Do not build thread or meeting context by directly spelunking raw landing JSON unless the access is encapsulated by the projection registry and recorded in coverage/access receipts.

Completion requires:

- email thread context derived from structured message/thread projections;
- calendar meeting context derived from structured event/attendee/recurrence projections;
- source-quality rollups visible in the context builder;
- no consumer fallback that silently prefers legacy redacted/metadata-only tables when structured full-raw projections are available.
