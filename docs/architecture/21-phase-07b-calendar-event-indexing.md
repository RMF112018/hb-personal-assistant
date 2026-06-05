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
- **apply**: as of record 148, events are normalized first, then
  `apply_calendar_index_batch` uses one SQLite connection/transaction for source registration, crawl
  receipt open/finalize, event rows, attendee rows, and sync state. Write failures roll back event/attendee
  rows and persist an explicit failed crawl/sync receipt with safe operation diagnostics.

## Guardrails proven (temp-DB apply smoke + tests)

- Dry-run persists nothing; apply persists 3 events / 1 attendee / 1 crawl receipt / 1 sync row.
- No raw subject/organizer/attendee/location/join-URL string in `calendar_event_index` or
  `calendar_event_attendees`; `subject_redacted` is the `[redacted:<16-hex>]` form.
- `raw_body_persisted` / `full_text_persisted` / `external_writeback_performed` CHECK columns all 0.
- Idempotent: re-running apply leaves event/attendee row counts unchanged (stable `event_index_id`);
  crawl-run receipts accumulate as an audit log.
- Read-only external posture preserved (only `get_me`/`list_calendarView` GETs via the guarded client);
  `graph/` static no-write-verb scan (`test_mutation_lockout`) still clean. No 07D readiness claimed.

## Larger-window reliability + per-event diagnostics (post-148 / Prompt 15 follow-up)

Follow-up hardens the apply path for larger windows (e.g. `--max-items 100/200`) while preserving the bounded date window + max cap and all no-raw guards.

- In `event_indexer.index` (post-fetch+normalize): event_records are chunked (size 100); each chunk is applied via the enhanced `apply_calendar_index_batch(..., chunked=True, is_final_chunk=..., partial_ok=True, failure_diagnostics=accum_list)`.
- Per-event errors inside a chunk tx are caught, appended to diags (`{"event_ordinal": N, "event_index_id": "<hash>", "operation": "event_upsert", "exception_type": "..." }`), and the chunk continues (prior events in chunk commit).
- After each chunk: crawl_run is updated (INSERT OR IGNORE + accum `events_indexed = COALESCE(...) + delta`; status 'checkpointed' for non-final, 'completed' for final chunk); `calendar_sync_state.last_attempted_sync_utc` + status updated every chunk.
- `IndexResult.status` may be `completed_with_errors` (with non-empty `failure_diagnostics`); `persisted=True` for with_errors cases (goods landed); top-level CLI "ok" stays True unless a source hard-failed.
- On structural failure for a chunk: diag collected; prior chunks' work remains (per-chunk tx safety); overall status failed only for unrecoverable (fetch etc).
- No change to client `list_calendar_view` (still always fetches the full bounded window; resume/re-work safety via idempotent ON CONFLICT on `event_index_id` + checkpoint visibility in crawl rows).
- Mail discover side (same Prompt): `project_discovery` now collects matches then single `apply_project_email_discover_batch` (1 tx for msgs+recips+matches+receipt+crawl/sync); per-project diags + `persistence` in report; `EmailDiscoverBatchApplyError` surfaced in CLI with redacted diag; failed receipt safe in sep tx.

**Guardrails unchanged**: date-bounded + max_items (never full calendar); $select excludes body/desc/join; normalize + CHECKs + guards ensure 0 raw; dry default; --apply explicit; read-only client; outside MCP; no writeback.

**Cites**: event_indexer:244 (chunk loop), repositories:1069 (enhanced batch with per-ev try + OR-IGNORE + COALESCE checkpoint), cli/graph:1969 (ok for partials), 04/148/00 for cross.

Verification in plan (bounded + larger dry/apply; targeted pytest; construction validate). See 148 for batch precedent, 00-README for 07B ledger.
