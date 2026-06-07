# Prompt 04 — Calendar Raw Content Ingestion

## Objective

Update calendar indexing to persist raw calendar content locally when raw-content mode is enabled.

## Tasks

1. Fetch/store subject, body, location, organizer, attendees, join URL, recurrence metadata.
2. Persist into `calendar_event_raw_content`.
3. Add endpoint and context packet access.
4. Add tests for private/cancelled/online meeting cases.

## Acceptance

- Dev calendar sync produces raw calendar rows.
- Meeting prep packet includes actual meeting subject/body/attendees.
