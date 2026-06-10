You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 03 — Calendar Full Raw Ingestion

## Objective

Harden calendar raw ingestion so `calendar_event_raw_content` becomes the durable local SQLite store for full useful event/agenda/attendee content when raw policy is enabled.

## Implementation targets

Inspect and update as repo truth dictates:

- `src/hb_assistant/construction/calendar/event_indexer.py`
- `src/hb_assistant/graph/calendar_readonly_client.py`
- `src/hb_assistant/graph/calendar_client.py` if still relevant to current CLI paths
- `src/hb_assistant/construction/calendar/endpoints.py`
- `src/hb_assistant/construction/meeting_prep/brief_builder.py`
- `src/hb_assistant/construction/store*`
- CLI commands under current graph/calendar modules

## Required behavior

1. Keep existing redacted `calendar_event_index` path intact.
2. For raw mode, fetch full event details by event ID using bounded, read-only Graph GET.
3. Persist to `calendar_event_raw_content`:
   - subject;
   - body text;
   - body HTML;
   - preview if available;
   - organizer name/email;
   - attendees with type/status/name/address;
   - location display and structured location if available;
   - online meeting provider;
   - join URL only under local-DB policy;
   - recurrence;
   - start/end/timezone;
   - created/updated/cancelled/private state where available;
   - source/project links;
   - payload hash;
   - source quality.
4. Classify source quality:
   - `graph_full_event_body` when body_text/body_html or full agenda body is present;
   - `graph_body_preview_only` when only preview is present;
   - `redacted_legacy_projection` when generated from old redacted rows;
   - `metadata_only` when no useful body/preview is available.
5. Lower-quality rows must not overwrite higher-quality rows.
6. Private/confidential event handling must be explicit. If policy permits local raw storage for private events, store locally but never emit outward by default; otherwise store metadata-only and classify honestly.

## Required tests

Synthetic Graph event fixtures must prove:

- full body text persists;
- full body HTML persists;
- attendee/organizer/location/recurrence persist;
- join URL policy is enforced;
- preview/metadata-only source-quality classes work;
- lower-quality rows cannot overwrite `graph_full_event_body`;
- status/evidence/stdout never emit synthetic raw agenda/body/join URL;
- raw access events are recorded for raw reads.

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/03_calendar_full_raw_ingestion.md
```

Use counts, hashes, source-quality distribution, and null rates only.
