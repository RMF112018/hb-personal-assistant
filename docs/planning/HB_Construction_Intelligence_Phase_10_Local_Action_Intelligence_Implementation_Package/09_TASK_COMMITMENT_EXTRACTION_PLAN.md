# 09 Task and Commitment Extraction Plan

## Purpose

Extract reviewable work candidates from approved email-thread summaries, calendar context, source records, Procore change records, and local read models.

## Input sources

- `email_thread_summary_materialization_runs`
- email thread summaries/read models
- `calendar_event_index`
- `meeting_email_relationship_candidates`
- `procore_live_records`
- `procore_action_signals`
- `source_system_record_map`
- existing Daily Brief packets

## Output classes

- request made to user;
- commitment made by user;
- question needing answer;
- decision needed;
- due date/deadline;
- meeting prep item;
- project risk signal;
- waiting on others;
- waiting on me.

## Required output fields

- candidate id;
- title;
- project key;
- assignee classification;
- due date;
- urgency;
- waiting state;
- safety category;
- source refs;
- confidence;
- model profile;
- prompt version;
- reason;
- recommended next action;
- review status.

## Acceptance

No accepted task or commitment may exist without at least one source reference.
