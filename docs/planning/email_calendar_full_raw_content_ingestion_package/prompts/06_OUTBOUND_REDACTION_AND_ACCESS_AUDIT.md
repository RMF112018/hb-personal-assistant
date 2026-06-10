You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 06 — Outbound Redaction and Access Audit

## Objective

Prove that local raw storage does not create raw leakage to outbound surfaces.

## Required implementation

1. Centralize or reuse a redaction/no-leak scanner for:
   - CLI stdout;
   - logs;
   - repo evidence;
   - browser/status JSON;
   - Obsidian outputs;
   - daily brief markdown/html/notification/open receipts;
   - model prompt/response receipts;
   - committed test snapshots.
2. Add raw access audit wrappers around raw read functions.
3. Ensure all raw endpoints default to metadata/redacted unless explicit policy and caller controls allow raw.
4. Ensure any browser/status endpoint exposes only:
   - counts;
   - null rates;
   - source-quality distribution;
   - hashes;
   - boolean raw-included markers;
   - pass/fail diagnostics.
5. Do not write raw body strings into evidence or logs while testing. Use synthetic marker strings only in isolated tests and assert they do not appear in outputs.

## Required no-leak scan patterns

At minimum scan for:

- synthetic fixture body sentinel strings;
- OAuth token-like values;
- refresh-token-like values;
- `Authorization: Bearer`;
- `@microsoft.graph.downloadUrl`;
- raw join URLs in evidence/status/logs/stdout;
- email body sentinel strings;
- calendar agenda sentinel strings.

## Tests

- Accessing raw email content logs `raw_content_access_events`.
- Accessing raw calendar content logs `raw_content_access_events`.
- CLI/status/evidence output does not include fixture raw body sentinels.
- Model packet receipts do not store raw prompts/responses unless a separate explicit policy says otherwise; for this package, they must not.

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/06_outbound_redaction_and_access_audit.md
```
