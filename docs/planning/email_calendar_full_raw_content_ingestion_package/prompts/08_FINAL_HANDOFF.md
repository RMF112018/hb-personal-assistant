You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 08 — Final Handoff

## Objective

Prepare a complete implementation handoff for Bobby after all code, tests, validation, and evidence are complete.

## Required final checks

Run the repo-appropriate full validation matrix. Include at minimum unless repo truth dictates otherwise:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
ruff check src tests
mypy src
python -m compileall src tests
pytest
python docs/planning/email_calendar_full_raw_content_ingestion_package/scripts/email_calendar_raw_probe.py \
  --repo /Users/bobbyfetting/hb-personal-assistant \
  --output /tmp/email-calendar-raw-probe-final.json
```

Run no-leak scans over evidence, logs produced by validation, CLI outputs captured in evidence, and relevant generated artifacts.

## Required final handoff content

Return exactly these sections:

```text
Branch / HEAD:
Commits:
Schema head before / after:
Files changed:
Implementation summary:
Email raw ingestion result:
Calendar raw ingestion result:
Thread / meeting projection result:
Consumer read-model result:
Tests run:
DB-copy validation summary:
No-leak proof summary:
Raw-content source-quality distribution:
Consumer before/after summary:
Production runbook path:
Evidence path:
Known limitations / deferred items:
Exact commands Bobby should run next:
```

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/08_final_handoff.md
```

No raw email/calendar content.

## Additional final handoff gate

Before writing the final handoff, confirm all of the following:

- projection matrix exists;
- field inventory exists;
- final structured projection tables exist;
- projection reprocess has run on fixtures and a `/tmp` DB copy;
- source-family coverage reports zero unmapped primary business fields for available raw rows;
- source-family coverage reports zero unmapped nested business fields for available raw rows;
- daily brief / meeting prep / model context consumers prefer the final structured projection layer;
- any source family with no raw rows is explicitly marked `no_raw_rows_available_in_current_copy` and not falsely reported as production-complete.
