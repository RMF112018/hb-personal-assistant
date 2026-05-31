# Phase 07B — Calendar Event Indexing (bounded calendarView → redacted SQLite)

**Phase:** 07B — Prompt 04 (Calendar Event Indexing)
**Status:** Implemented (bounded read-only indexer; project matching/classification/Obsidian land in 07B Prompts 05–10).
Evidence: `docs/evidence/construction-intelligence-phase-07b-calendar-email/04-calendar-ingestion-dry-run.json`.

Adds the writer for the (previously empty) V23 calendar tables: a bounded `calendarView` indexer that
reads through the Prompt 03 guarded `ReadOnlyCalendarClient` and persists **only redacted/hashed
metadata** to local SQLite, gated behind `--apply` (dry-run default). No event body/description or
online-meeting join URL is fetched or stored. No project matching, classification, or Obsidian output.

## Components

| Component | Path | Role |
|---|---|---|
| Normalizer + indexer | `src/hb_assistant/construction/calendar/event_indexer.py` | `normalize_event()` (raw Graph event → redacted index kwargs + attendee rows), `CalendarEventIndexer.index()` (dry-run/apply), `IndexResult` |
| Repository writers | `src/hb_assistant/construction/store/repositories.py` | `insert_/complete_calendar_crawl_run`, `upsert_calendar_event_index`, `upsert_calendar_event_attendee` |
| CLI | `src/hb_assistant/cli/graph.py` (`graph calendar index`) | `--dry-run/--apply` (default dry-run), `--lookback-days/--lookahead-days/--max-items/--project/--json` |

Reuses the canonical redaction helpers (`hash_value` 16-char sha256, `redact_subject`,
`redact_location` in `normalize/redaction.py`; `_domain` pattern from the email indexer) and mirrors
the `EmailMessageIndexer` dry-run/apply flow and the `insert_/complete_email_crawl_run` receipt pattern.
It deliberately does **not** reuse `normalize/calendar_event.py` (that model carries an
`online_meeting_link`/joinUrl field and lacks the V23 hash columns); the new normalizer is
body-/join-URL-free by construction.

## Normalizer mapping (raw Graph event → redacted columns)

| Graph field | Stored column | Transform |
|---|---|---|
| `id` | `graph_event_id_hash`, `event_index_id` | `hash_value(id)`; `event_index_id = hash_value("{source_id}|{event_id_hash}")` (stable → idempotent) |
| `iCalUId` / `seriesMasterId` / `webLink` | `ical_uid_hash` / `series_master_id_hash` / `web_link_hash` | `hash_value` |
| `subject` | `subject_hash`, `subject_redacted`, `subject_token_hashes_json` | hash + `[redacted:…]` + JSON list of hashed tokens (non-private only) |
| `organizer.emailAddress.address` | `organizer_hash`, `organizer_domain` | `hash_value` + domain (non-private only) |
| `attendees[].emailAddress.address` | `calendar_event_attendees` rows | `attendee_hash` + domain + `type`/`status.response` (non-private only) |
| `location.displayName` | `location_hash`, `location_redacted` | hash + `[redacted:…]` (non-private only) |
| `start/end.dateTime`, `start.timeZone` | `start_datetime_utc`, `end_datetime_utc`, `timezone` | pass-through (event skipped if start/end missing) |
| `isCancelled` / `sensitivity` / `isOnlineMeeting` | `is_cancelled` / `is_private` / `is_online_meeting` | bool; `is_private = sensitivity in {private, confidential}` |
| `onlineMeetingProvider` | `online_meeting_provider` | pass-through (safe flag) |
| `onlineMeeting.joinUrl` | — | **never fetched, never stored** |
| `hasAttachments` | `has_attachments` | bool |

`project_key`/`project_match_*` are left NULL (Prompt 05).

## Private / cancelled / online handling

- **Private** (`sensitivity in {private, confidential}`): minimal metadata only — id hashes, time
  window, flags. Subject/organizer/location columns and attendee rows are omitted; `review_required=1`,
  `review_reasons_json=["private_event"]`. (Per user decision, sensitive-category keyword review is
  deferred to the classifier prompt; index-time review is private-events-only.)
- **Cancelled**: `is_cancelled=1`; otherwise indexed normally (counted in `events_cancelled`).
- **Online**: `is_online_meeting=1` + `online_meeting_provider`; the join URL is never represented.

## Dry-run / apply flow

- **dry-run** (default): reads the window, tallies `events_seen/private/cancelled/review`, returns a
  safe sample (event_index_id + time window + flags — no raw values), and writes **nothing**.
- **apply**: `upsert_calendar_source_location` (FK parent; owner resolved via `get_me()` →
  `hash_value(upn)`) → `insert_calendar_crawl_run` → per event `upsert_calendar_event_index` + attendee
  upserts → `complete_calendar_crawl_run` (counters) → `upsert_calendar_sync_state`. Graph/read failures
  are caught and recorded as a sanitized `error_redacted` with `status="failed"` — the command still
  returns `ok:true`/exit 0 (dry-run validation stays green even with an expired token).

## Guardrails proven (temp-DB apply smoke + tests)

- Dry-run persists nothing; apply persists 3 events / 1 attendee / 1 crawl receipt / 1 sync row.
- No raw subject/organizer/attendee/location/join-URL string in `calendar_event_index` or
  `calendar_event_attendees`; `subject_redacted` is the `[redacted:<16-hex>]` form.
- `raw_body_persisted` / `full_text_persisted` / `external_writeback_performed` CHECK columns all 0.
- Idempotent: re-running apply leaves event/attendee row counts unchanged (stable `event_index_id`);
  crawl-run receipts accumulate as an audit log.
- Read-only external posture preserved (only `get_me`/`list_calendarView` GETs via the guarded client);
  `graph/` static no-write-verb scan (`test_mutation_lockout`) still clean. No 07D readiness claimed.
