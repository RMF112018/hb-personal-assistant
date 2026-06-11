You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 07 — DB Copy Validation and Evidence

## Objective

Validate the implemented transition on fixtures and on a `/tmp` copy of Bobby's production DB without mutating the production DB during validation.

## Required commands

Use the package probe:

```bash
python docs/planning/email_calendar_full_raw_content_ingestion_package/scripts/email_calendar_raw_probe.py \
  --repo /Users/bobbyfetting/hb-personal-assistant \
  --output /tmp/email-calendar-raw-probe.json
```

The script must resolve the production DB path through `PathPolicy().get_db_path()` unless `--db-path` is supplied. It must copy the DB to `/tmp` and run read-only checks against the copy.

## Structured projection validation addendum

In addition to the raw-row matrices, produce projection coverage matrices:

```text
source_family | raw_table | raw_parent_rows | structured_parent_table | structured_parent_rows | parent_match_verdict
email_message | email_message_raw_content | ... | <implemented message projection table> | ... | ...
email_thread | email_thread_raw_context | ... | <implemented thread projection table> | ... | ...
calendar_event | calendar_event_raw_content | ... | <implemented event projection table> | ... | ...
```

And:

```text
source_family | nested_path_family | observed_parent_rows | child_table | child_rows | mapped_paths | unmapped_paths | verdict
email_message | to_recipients_json[] | ... | <recipient child table> | ... | ... | 0 | ...
email_message | attachment_metadata_json[] | ... | <attachment child table> | ... | ... | 0 | ...
email_thread | messages_json[] | ... | <thread/message bridge or sidecar> | ... | ... | 0 | ...
calendar_event | attendees_json[] | ... | <attendee child table> | ... | ... | 0 | ...
calendar_event | recurrence_json | ... | <recurrence table or sidecar> | ... | ... | 0 | ...
```

The DB-copy validation fails if any source family with available raw rows reports unmapped primary or nested business fields. Raw landing row counts alone are not evidence of completion.

## Required DB-copy matrices

Produce, at minimum:

```text
surface | table | rows | body_preview_non_null | body_text_non_null | body_html_non_null | source_quality | verdict
email | emails | ... | ... | ... | ... | ... | ...
email | email_message_raw_content | ... | ... | ... | ... | ... | ...
email | email_thread_raw_context | ... | ... | ... | ... | ... | ...
calendar | calendar_events | ... | ... | ... | ... | ... | ...
calendar | calendar_event_raw_content | ... | ... | ... | ... | ... | ...
```

And:

```text
consumer | before source | after source | before usefulness blocker | after improvement | verdict
daily brief email follow-ups | ... | ... | ... | ... | ...
daily brief meeting prep | ... | ... | ... | ... | ...
model context packets | ... | ... | ... | ... | ...
relationship extraction | ... | ... | ... | ... | ...
search/retrieval | ... | ... | ... | ... | ...
```

## Validation expectations

- Production DB mtime/hash unchanged during audit/validation.
- `/tmp` copy is clearly named and deleted or retained only under `/tmp`.
- Evidence contains only counts/hashes/null rates/source-quality distributions.
- No raw body content appears in evidence.

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/07_db_copy_validation_and_evidence.md
```

Attach summarized `/tmp/email-calendar-raw-probe.json` fields only; do not paste raw rows.
