You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 02 — Email Full Raw Ingestion

## Objective

Harden email raw ingestion so `email_message_raw_content` becomes the durable local SQLite store for full useful email business content when raw policy is enabled.

## Implementation targets

Inspect and update as repo truth dictates:

- `src/hb_assistant/construction/email/message_indexer.py`
- `src/hb_assistant/graph/mail_readonly_client.py`
- `src/hb_assistant/graph/mail_client.py` if still relevant to current CLI paths
- `src/hb_assistant/construction/email/endpoints.py`
- `src/hb_assistant/construction/store*`
- CLI commands under `src/hb_assistant/cli/graph.py` or current graph/email command modules

## Required behavior

1. Full body fetch is bounded and opt-in through policy/config/operator flag.
2. Body fetch uses Graph read-only GET only.
3. Persist to `email_message_raw_content`:
   - subject;
   - body preview;
   - body text;
   - body HTML;
   - content type if available;
   - sender name/address;
   - to/cc/bcc recipients;
   - sent/received timestamps;
   - conversation/thread identifiers or hashes;
   - attachment metadata only;
   - source/project links;
   - payload hash;
   - source quality.
4. Classify source quality:
   - `graph_full_body` when body_text or body_html is present from Graph full body;
   - `graph_body_preview_only` when only preview is available;
   - `redacted_legacy_projection` when generated from older redacted projections;
   - `metadata_only` when no useful body/preview is available.
5. Do not store access tokens, refresh tokens, auth headers, client secrets, credential-cache contents, or signed URLs.
6. Do not download attachment content in this package.
7. Lower-quality rows must not overwrite existing higher-quality rows.
8. Raw email ingestion run counts must be available without raw text.

## Required tests

Use synthetic Graph message fixtures. Tests must prove:

- full text body persists;
- full HTML body persists;
- preview-only is classified correctly;
- lower-quality legacy/preview rows cannot overwrite `graph_full_body`;
- attachment metadata persists but attachment content does not;
- stdout/status/evidence serializers do not print synthetic raw body strings;
- raw access events are written when raw read paths are invoked.

## Validation commands

Run focused tests first, then broader suite per repo norms:

```bash
pytest tests -k "email and raw" -q
ruff check src tests
mypy src
python -m compileall src tests
```

Adjust exact selectors to repo truth; document all commands run.

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/02_email_full_raw_ingestion.md
```

No raw body strings. Counts/hashes/source-quality distribution only.
