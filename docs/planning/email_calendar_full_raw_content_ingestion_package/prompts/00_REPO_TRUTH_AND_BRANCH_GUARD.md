You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 00 — Repo Truth and Branch Guard

## Objective

Establish a clean, current repo baseline and verify the current code/schema reality before implementing anything.

## Tasks

1. `cd /Users/bobbyfetting/hb-personal-assistant`.
2. Capture:
   - `git status --short`
   - `git branch --show-current`
   - `git rev-parse HEAD`
   - `git log --oneline --decorate -15`
3. Create a new branch from current main unless Bobby has explicitly provided another branch name:
   - suggested: `fix/email-calendar-full-raw-content-ingestion`
4. Confirm current schema head by inspecting `src/hb_assistant/store/migrator.py` and running the repo's schema validation command if available.
5. Search repo truth:

```bash
grep -R "email_message_raw_content\|email_thread_raw_context\|calendar_event_raw_content\|raw_content_policy_state\|raw_content_model_context_packets\|raw_content_access_events" -n src tests docs | head -300
grep -R "body_text\|body_html\|bodyPreview\|body_preview\|full_body\|persist_full_body\|source_quality" -n src tests docs | head -300
grep -R "Mail.Read\|Calendars.Read\|messages\|calendarView\|onlineMeeting\|attendees\|recurrence" -n src tests docs | head -300
grep -R "meeting prep\|meeting_prep\|daily brief\|daily_brief\|relationship\|model context\|raw_content" -n src/hb_assistant tests docs | head -300
```

6. Confirm whether `src/hb_assistant/resources/sqlite-schema.sql` exists locally. If absent, document that migrator is the current canonical DDL source.
7. Do not change files in this prompt except a small evidence note under the evidence directory.

## Deliverable

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/00_repo_truth_and_branch_guard.md
```

Include only commands, SHAs, file paths, table/column names, and counts. No raw bodies.

## Stop conditions

Stop if the tree is dirty with unrelated changes that cannot be safely isolated.
