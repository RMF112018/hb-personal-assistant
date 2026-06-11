# 04 — Thread and Meeting Context Projection

Thread and meeting context are derived from the **final structured projection layer**, not by
spelunking raw landing JSON.

## Email thread context

`email_raw_thread_structured` (+ `email_raw_thread_messages_structured` child) is built from
persisted `email_thread_raw_context` rows and survives process restart. The thread projection
carries `message_count`, `participant_count`, `has_full_body`, a source-quality rollup, and a
lossless `source_refs_sidecar_json`. Consumers reach it via `select_thread_context` (structured
preferred; source-quality visible). Fixture proof: `test_thread_projects_from_persisted_rows`.

## Calendar meeting context

`MeetingPrepBriefBuilder._section_meeting_context` sources agenda/attendee detail from
`calendar_raw_event_structured` (+ attendees child) via `select_event_context`. The persisted
`meeting_prep_brief_sections.section_redacted` carries:

```text
selected_source, source_quality, subject, location, organizer, attendees[role/name/domain],
attendee_count, has_agenda_body (flag), agenda_body_chars, has_join_url (flag),
online_meeting_provider, start, end
```

It no longer persists the agenda body, HTML, or join URL (those stay local-private in the raw
table / explicit model packets). Source-quality rollups are visible; there is no silent fallback to
the legacy `calendar_event_index` metadata when a structured event row exists. Fixture proof:
`test_meeting_prep_uses_structured_and_no_leak`.
